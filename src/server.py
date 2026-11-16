import argparse
import copy
import json
import logging
import selectors
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("GameServer")

# ============================================================================
# FSM State Definitions & Message Types (Sprint 1 Specification)
# ============================================================================
STATE_WAITING_FOR_PLAYERS = "WaitingForPlayers"
STATE_GAME_ACTIVE = "GameActive"
STATE_PLAYER_X_TURN = "PlayerXTurn"
STATE_PLAYER_O_TURN = "PlayerOTurn"
STATE_INVALID_MOVE = "InvalidMove"
STATE_X_WINS = "XWins"
STATE_O_WINS = "OWins"
STATE_DRAW = "Draw"
STATE_TERMINATED = "Terminated"

MSG_CONNECT = "CONNECT"
MSG_LOBBY_WAIT = "LOBBY_WAIT"
MSG_GAME_START = "GAME_START"
MSG_MOVE = "MOVE"
MSG_STATE_UPDATE = "STATE_UPDATE"
MSG_GAME_OVER = "GAME_OVER"
MSG_DISCONNECT = "DISCONNECT"
MSG_ERROR = "ERROR"

ERR_OUT_OF_TURN = "OUT_OF_TURN"
ERR_INVALID_CELL = "INVALID_CELL"
ERR_MALFORMED = "MALFORMED_PACKET"
ERR_GAME_NOT_ACTIVE = "GAME_NOT_ACTIVE"


# ============================================================================
# Client Session Container
# ============================================================================
class ClientSession:
    """Encapsulates a connected client socket and protocol buffer."""

    def __init__(self, sock: socket.socket, addr: Tuple[str, int], player_id: str):
        self.sock = sock
        self.addr = addr
        self.player_id = player_id          # e.g., "Player_1", "Player_2"
        self.player_name = player_id        # Display name from CONNECT
        self.role: Optional[str] = None     # "X" or "O"
        self.recv_buffer = ""               # Accumulator for newline-delimited framing


# ============================================================================
# Authoritative Game State Engine (FSM & Concurrency Discipline)
# ============================================================================
class TicTacToeEngine:
    """Thread-safe authoritative game state engine enforcing the game FSM."""

    def __init__(self):
        # Mutual exclusion lock protecting shared game state
        self.state_lock = threading.Lock()
        self.reset_game()

    def reset_game(self) -> None:
        """Reset board and state machine back to initial state."""
        with self.state_lock:
            self.state = STATE_WAITING_FOR_PLAYERS
            self.board: List[List[str]] = [
                ["-", "-", "-"],
                ["-", "-", "-"],
                ["-", "-", "-"]
            ]
            self.current_turn = "Player_1"  # Player_1 moves first (X)
            self.current_role = "X"
            self.scores: Dict[str, int] = {"Player_1": 0, "Player_2": 0}
            self.seq = 0                    # Monotonic state update sequence counter
            self.player_roles: Dict[str, str] = {}  # {player_id: "X"/"O"}

    def initialize_game(self, player1_id: str, player2_id: str) -> Dict[str, Any]:
        """Transitions FSM from WaitingForPlayers to GameActive -> PlayerXTurn."""
        with self.state_lock:
            self.state = STATE_GAME_ACTIVE
            self.board = [
                ["-", "-", "-"],
                ["-", "-", "-"],
                ["-", "-", "-"]
            ]
            self.current_turn = player1_id
            self.current_role = "X"
            self.player_roles = {
                player1_id: "X",
                player2_id: "O"
            }
            if player1_id not in self.scores:
                self.scores[player1_id] = 0
            if player2_id not in self.scores:
                self.scores[player2_id] = 0

            # Transition to PlayerXTurn
            self.state = STATE_PLAYER_X_TURN
            self.seq += 1

            snapshot = {
                "state": self.state,
                "board": copy.deepcopy(self.board),
                "active_player": self.current_turn,
                "active_role": self.current_role,
                "scores": copy.deepcopy(self.scores),
                "seq": self.seq,
                "player_roles": copy.deepcopy(self.player_roles)
            }
            logger.info("FSM: WaitingForPlayers -> GameActive -> PlayerXTurn (seq=%d)", self.seq)
            return snapshot

    def check_winner(self) -> Optional[str]:
        """Evaluates 3-in-a-row rows, columns, and diagonals for winner ('X' or 'O')."""
        b = self.board
        # Check rows
        for r in range(3):
            if b[r][0] != "-" and b[r][0] == b[r][1] == b[r][2]:
                return b[r][0]
        # Check columns
        for c in range(3):
            if b[0][c] != "-" and b[0][c] == b[1][c] == b[2][c]:
                return b[0][c]
        # Check diagonals
        if b[0][0] != "-" and b[0][0] == b[1][1] == b[2][2]:
            return b[0][0]
        if b[0][2] != "-" and b[0][2] == b[1][1] == b[2][0]:
            return b[0][2]
        return None

    def is_board_full(self) -> bool:
        return all(self.board[r][c] != "-" for r in range(3) for c in range(3))

    def process_move(self, player_id: str, row: int, col: int) -> Tuple[bool, str, Dict[str, Any]]:
        """Validates and executes a player move according to the FSM.

        All state mutations are executed inside `with self.state_lock:`.
        Returns:
            (success, outcome_type, snapshot_data)
            where outcome_type is one of:
            - "STATE_UPDATE": valid move made, game continues
            - "GAME_OVER": win or draw reached
            - "ERROR": invalid move or out of turn
        """
        with self.state_lock:
            # 1. Validate game is currently active
            if self.state not in (STATE_PLAYER_X_TURN, STATE_PLAYER_O_TURN):
                return False, "ERROR", {
                    "error_code": ERR_GAME_NOT_ACTIVE,
                    "error_message": f"Game is not in active play state (Current state: {self.state})."
                }

            # 2. Validate turn entitlement (Authoritative Out-of-turn rejection)
            if player_id != self.current_turn:
                prev_state = self.state
                self.state = STATE_INVALID_MOVE
                logger.warning("FSM: %s -> InvalidMove (Attempt by %s during %s's turn)",
                               prev_state, player_id, self.current_turn)
                # Revert FSM back to active turn without state mutation
                self.state = prev_state
                return False, "ERROR", {
                    "error_code": ERR_OUT_OF_TURN,
                    "error_message": f"It is not your turn. Current turn: {self.current_turn}."
                }

            # 3. Validate coordinates and board boundaries
            if not (0 <= row <= 2 and 0 <= col <= 2):
                prev_state = self.state
                self.state = STATE_INVALID_MOVE
                self.state = prev_state
                return False, "ERROR", {
                    "error_code": ERR_INVALID_CELL,
                    "error_message": f"Cell ({row}, {col}) is out of bounds [0-2]."
                }

            # 4. Validate cell emptiness
            if self.board[row][col] != "-":
                prev_state = self.state
                self.state = STATE_INVALID_MOVE
                logger.warning("FSM: %s -> InvalidMove (Cell [%d, %d] already occupied)",
                               prev_state, row, col)
                self.state = prev_state
                return False, "ERROR", {
                    "error_code": ERR_INVALID_CELL,
                    "error_message": f"Cell ({row}, {col}) is already occupied by '{self.board[row][col]}'."
                }

            # 5. Commit move mutation
            symbol = self.player_roles.get(player_id, "X")
            self.board[row][col] = symbol
            self.seq += 1

            # 6. Evaluate victory or draw conditions
            winner_symbol = self.check_winner()
            if winner_symbol:
                if winner_symbol == "X":
                    self.state = STATE_X_WINS
                else:
                    self.state = STATE_O_WINS

                self.scores[player_id] = self.scores.get(player_id, 0) + 1
                logger.info("FSM: Move committed -> %s (%s wins!)", self.state, player_id)

                snapshot = {
                    "result": f"{player_id}_Wins",
                    "winner": player_id,
                    "winner_symbol": winner_symbol,
                    "final_board": copy.deepcopy(self.board),
                    "scores": copy.deepcopy(self.scores),
                    "seq": self.seq
                }
                # Transition to Terminated
                self.state = STATE_TERMINATED
                logger.info("FSM: Game ended -> Terminated")
                return True, "GAME_OVER", snapshot

            if self.is_board_full():
                self.state = STATE_DRAW
                logger.info("FSM: Move committed -> Draw (Board full)")
                snapshot = {
                    "result": "Draw",
                    "winner": "None",
                    "winner_symbol": None,
                    "final_board": copy.deepcopy(self.board),
                    "scores": copy.deepcopy(self.scores),
                    "seq": self.seq
                }
                self.state = STATE_TERMINATED
                logger.info("FSM: Game ended -> Terminated")
                return True, "GAME_OVER", snapshot

            # 7. Toggle turn to next player
            if self.state == STATE_PLAYER_X_TURN:
                self.state = STATE_PLAYER_O_TURN
                self.current_role = "O"
            else:
                self.state = STATE_PLAYER_X_TURN
                self.current_role = "X"

            # Find next player_id
            for pid, r in self.player_roles.items():
                if r == self.current_role:
                    self.current_turn = pid
                    break

            logger.info("FSM: Valid move [%d, %d] by %s. Next: %s (%s), seq=%d",
                        row, col, player_id, self.current_turn, self.current_role, self.seq)

            snapshot = {
                "board": copy.deepcopy(self.board),
                "active_player": self.current_turn,
                "active_role": self.current_role,
                "scores": copy.deepcopy(self.scores),
                "seq": self.seq
            }
            return True, "STATE_UPDATE", snapshot

    def handle_disconnect_forfeit(self, disconnected_player_id: str) -> Optional[Dict[str, Any]]:
        """Handles unexpected disconnect during game play.

        Awards forfeit victory to the remaining player and transitions to Terminated.
        """
        with self.state_lock:
            if self.state in (STATE_PLAYER_X_TURN, STATE_PLAYER_O_TURN, STATE_GAME_ACTIVE):
                remaining_player = None
                for pid in self.player_roles:
                    if pid != disconnected_player_id:
                        remaining_player = pid
                        break

                if remaining_player:
                    self.scores[remaining_player] = self.scores.get(remaining_player, 0) + 1
                    symbol = self.player_roles.get(remaining_player, "X")
                    self.state = STATE_X_WINS if symbol == "X" else STATE_O_WINS
                    logger.info("FSM: Disconnect forfeit by %s -> %s wins",
                                disconnected_player_id, remaining_player)

                    snapshot = {
                        "result": f"{remaining_player}_Wins",
                        "winner": remaining_player,
                        "winner_symbol": symbol,
                        "final_board": copy.deepcopy(self.board),
                        "scores": copy.deepcopy(self.scores),
                        "seq": self.seq + 1,
                        "reason": f"Opponent {disconnected_player_id} disconnected."
                    }
                    self.state = STATE_TERMINATED
                    return snapshot

            self.state = STATE_TERMINATED
            return None


# ============================================================================
# Non-blocking Multiplexed Server Application (Sprint 2 Architecture)
# ============================================================================
class GameServer:
    """Manages network socket multiplexing and client lifecycle."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.selector = selectors.DefaultSelector()
        self.engine = TicTacToeEngine()
        self.sessions: Dict[socket.socket, ClientSession] = {}
        self.clients_in_order: List[ClientSession] = []

    def start(self) -> None:
        """Initializes TCP listening socket and enters event-driven polling loop."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Avoid TIME_WAIT address conflicts
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen()
        server_sock.setblocking(False)

        # Register listening socket for accept events
        self.selector.register(server_sock, selectors.EVENT_READ, data=None)
        logger.info("Tic-Tac-Toe Server started. Listening on %s:%d (non-blocking I/O multiplexing)",
                    self.host, self.port)

        try:
            while True:
                # Poll registered sockets
                events = self.selector.select(timeout=1.0)
                for key, mask in events:
                    if key.data is None:
                        # New connection on listening socket
                        self._accept_connection(key.fileobj)
                    else:
                        # Data available on client socket
                        self._service_connection(key, mask)
        except KeyboardInterrupt:
            logger.info("Server shutting down by KeyboardInterrupt...")
        finally:
            self._cleanup_all()

    def _accept_connection(self, server_sock: socket.socket) -> None:
        """Accepts an incoming TCP connection from a client."""
        client_sock, addr = server_sock.accept()
        client_sock.setblocking(False)

        if len(self.clients_in_order) >= 2:
            logger.warning("Room full. Rejecting connection from %s", addr)
            err_msg = {
                "msg_type": MSG_ERROR,
                "player_id": "SERVER",
                "payload": {
                    "error_code": "ROOM_FULL",
                    "error_message": "Game room already has 2 players."
                },
                "timestamp": int(time.time())
            }
            self._send_raw(client_sock, err_msg)
            client_sock.close()
            return

        assigned_id = f"Player_{len(self.clients_in_order) + 1}"
        session = ClientSession(client_sock, addr, assigned_id)
        self.sessions[client_sock] = session
        self.clients_in_order.append(session)

        self.selector.register(client_sock, selectors.EVENT_READ, data=session)
        logger.info("Accepted connection from %s, assigned: %s", addr, assigned_id)

    def _service_connection(self, key: selectors.SelectorKey, mask: int) -> None:
        """Reads incoming wire stream, accumulates chunks, and splits on newlines."""
        client_sock = key.fileobj
        session: ClientSession = key.data

        try:
            chunk = client_sock.recv(1024)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError) as e:
            logger.warning("Abrupt socket drop on %s (%s): %s", session.player_id, session.addr, e)
            self._handle_client_disconnect(session)
            return

        # Critical POSIX rule: 0 bytes indicates clean EOF from remote FIN handshake
        if not chunk:
            logger.info("Received 0-byte EOF from %s (%s). Remote closed connection.",
                        session.player_id, session.addr)
            self._handle_client_disconnect(session)
            return

        # Append decoded chunk to accumulator
        session.recv_buffer += chunk.decode("utf-8", errors="replace")

        # Split on newline framing
        while "\n" in session.recv_buffer:
            line, session.recv_buffer = session.recv_buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            self._process_framed_message(session, line)

    def _process_framed_message(self, session: ClientSession, raw_line: str) -> None:
        """Parses a complete JSON frame and executes state transitions."""
        try:
            msg = json.loads(raw_line)
        except json.JSONDecodeError as err:
            logger.error("JSON decode error from %s: %s", session.player_id, err)
            err_resp = {
                "msg_type": MSG_ERROR,
                "player_id": "SERVER",
                "payload": {
                    "error_code": ERR_MALFORMED,
                    "error_message": f"Malformed JSON: {err}"
                },
                "timestamp": int(time.time())
            }
            self._send_raw(session.sock, err_resp)
            return

        msg_type = msg.get("msg_type")
        logger.info("Received [%s] from %s", msg_type, session.player_id)

        if msg_type == MSG_CONNECT:
            self._handle_connect(session, msg)
        elif msg_type == MSG_MOVE:
            self._handle_move(session, msg)
        elif msg_type == MSG_DISCONNECT:
            self._handle_disconnect_message(session)
        else:
            logger.warning("Unknown message type '%s' from %s", msg_type, session.player_id)
            err_resp = {
                "msg_type": MSG_ERROR,
                "player_id": "SERVER",
                "payload": {
                    "error_code": "UNKNOWN_MSG_TYPE",
                    "error_message": f"Unknown message type '{msg_type}'."
                },
                "timestamp": int(time.time())
            }
            self._send_raw(session.sock, err_resp)

    def _handle_connect(self, session: ClientSession, msg: Dict[str, Any]) -> None:
        """Processes player CONNECT and initiates lobby wait or game start."""
        player_name = msg.get("player_id", session.player_id)
        session.player_name = player_name

        if len(self.clients_in_order) == 1:
            # First player waiting in lobby
            wait_msg = {
                "msg_type": MSG_LOBBY_WAIT,
                "player_id": "SERVER",
                "payload": {
                    "your_player_id": session.player_id,
                    "waiting_for": "Player_2"
                },
                "timestamp": int(time.time())
            }
            self._send_raw(session.sock, wait_msg)
            logger.info("Sent LOBBY_WAIT to %s", session.player_id)
        elif len(self.clients_in_order) == 2:
            # Both players joined: initialize game session
            p1 = self.clients_in_order[0]
            p2 = self.clients_in_order[1]
            p1.role = "X"
            p2.role = "O"

            # 1. State machine initialization
            snapshot = self.engine.initialize_game(p1.player_id, p2.player_id)

            # 2. Dispatch GAME_START customized with your_player_id to each client
            for session_item in (p1, p2):
                start_msg = {
                    "msg_type": MSG_GAME_START,
                    "player_id": "SERVER",
                    "payload": {
                        "your_player_id": session_item.player_id,
                        "your_role": session_item.role,
                        "player_roles": {
                            p1.player_id: "X",
                            p2.player_id: "O"
                        },
                        "player_names": {
                            p1.player_id: p1.player_name,
                            p2.player_id: p2.player_name
                        },
                        "starting_player": p1.player_id
                    },
                    "timestamp": int(time.time())
                }
                self._send_raw(session_item.sock, start_msg)

            # 3. Dispatch initial STATE_UPDATE
            state_msg = {
                "msg_type": MSG_STATE_UPDATE,
                "player_id": "SERVER",
                "payload": {
                    "board": snapshot["board"],
                    "active_player": snapshot["active_player"],
                    "active_role": snapshot["active_role"],
                    "scores": snapshot["scores"],
                    "seq": snapshot["seq"]
                },
                "timestamp": int(time.time())
            }
            # Note: broadcast occurs OUTSIDE state_lock
            self._broadcast(state_msg)

    def _handle_move(self, session: ClientSession, msg: Dict[str, Any]) -> None:
        """Processes player MOVE intent and applies authoritative validation."""
        payload = msg.get("payload", {})
        row = payload.get("row")
        col = payload.get("col")

        if row is None or col is None or not isinstance(row, int) or not isinstance(col, int):
            err_msg = {
                "msg_type": MSG_ERROR,
                "player_id": "SERVER",
                "payload": {
                    "error_code": ERR_MALFORMED,
                    "error_message": "MOVE payload must include integer 'row' and 'col'."
                },
                "timestamp": int(time.time())
            }
            self._send_raw(session.sock, err_msg)
            return

        # Execute move against authoritative engine under state_lock
        success, outcome, snapshot = self.engine.process_move(session.player_id, row, col)

        # Broadcast or respond OUTSIDE the lock
        if not success:
            err_msg = {
                "msg_type": MSG_ERROR,
                "player_id": "SERVER",
                "payload": snapshot,
                "timestamp": int(time.time())
            }
            self._send_raw(session.sock, err_msg)
            return

        if outcome == "STATE_UPDATE":
            update_msg = {
                "msg_type": MSG_STATE_UPDATE,
                "player_id": "SERVER",
                "payload": {
                    "board": snapshot["board"],
                    "active_player": snapshot["active_player"],
                    "active_role": snapshot["active_role"],
                    "scores": snapshot["scores"],
                    "seq": snapshot["seq"]
                },
                "timestamp": int(time.time())
            }
            self._broadcast(update_msg)
        elif outcome == "GAME_OVER":
            over_msg = {
                "msg_type": MSG_GAME_OVER,
                "player_id": "SERVER",
                "payload": {
                    "result": snapshot["result"],
                    "final_board": snapshot["final_board"],
                    "winner": snapshot["winner"],
                    "winner_symbol": snapshot["winner_symbol"],
                    "scores": snapshot["scores"],
                    "seq": snapshot["seq"]
                },
                "timestamp": int(time.time())
            }
            self._broadcast(over_msg)

    def _handle_disconnect_message(self, session: ClientSession) -> None:
        """Handles graceful application-level DISCONNECT message from a client."""
        logger.info("Client %s sent clean DISCONNECT.", session.player_id)
        self._handle_client_disconnect(session)

    def _handle_client_disconnect(self, session: ClientSession) -> None:
        """Performs teardown on disconnected client and notifies opponent."""
        client_sock = session.sock

        # Unregister from selector and close socket
        if client_sock in self.sessions:
            del self.sessions[client_sock]
        if session in self.clients_in_order:
            self.clients_in_order.remove(session)

        try:
            self.selector.unregister(client_sock)
        except (KeyError, ValueError):
            pass

        try:
            client_sock.close()
        except OSError:
            pass

        logger.info("Socket closed for %s.", session.player_id)

        # Notify remaining player of forfeit win if game was in progress
        snapshot = self.engine.handle_disconnect_forfeit(session.player_id)
        if snapshot:
            over_msg = {
                "msg_type": MSG_GAME_OVER,
                "player_id": "SERVER",
                "payload": {
                    "result": snapshot["result"],
                    "final_board": snapshot["final_board"],
                    "winner": snapshot["winner"],
                    "winner_symbol": snapshot["winner_symbol"],
                    "scores": snapshot["scores"],
                    "seq": snapshot["seq"],
                    "reason": snapshot.get("reason", "Opponent disconnected")
                },
                "timestamp": int(time.time())
            }
            self._broadcast(over_msg)

        # Reset engine if no players remain
        if not self.clients_in_order:
            logger.info("All clients disconnected. Resetting game room to WaitingForPlayers.")
            self.engine.reset_game()

    def _send_raw(self, sock: socket.socket, msg_dict: Dict[str, Any]) -> bool:
        """Serializes message to JSON and transmits newline-delimited frame."""
        try:
            data = (json.dumps(msg_dict) + "\n").encode("utf-8")
            sock.sendall(data)
            return True
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError) as e:
            logger.warning("Error transmitting frame to socket: %s", e)
            return False

    def _broadcast(self, msg_dict: Dict[str, Any], exclude_sock: Optional[socket.socket] = None) -> None:
        """Broadcasts a framed message to all currently connected clients."""
        for session in list(self.clients_in_order):
            if session.sock != exclude_sock:
                self._send_raw(session.sock, msg_dict)

    def _cleanup_all(self) -> None:
        """Closes all open sockets and selectors during shutdown."""
        logger.info("Cleaning up all sockets and selector registrations...")
        for sock in list(self.sessions.keys()):
            try:
                self.selector.unregister(sock)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
        self.selector.close()
        logger.info("Server shutdown complete.")


# ============================================================================
# CLI Argument Parser (30 Points)
# ============================================================================
def parse_arguments() -> argparse.Namespace:
    """Parses command line arguments according to Section 2.1."""
    parser = argparse.ArgumentParser(
        description="CS 457 Tic-Tac-Toe Game Server (Sprint 3)"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        required=True,
        help="Listening port (binds to 0.0.0.0)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    # Listening port validation
    if not (1 <= args.port <= 65535):
        print(f"[ERROR] Port {args.port} is invalid. Port must be between 1 and 65535.")
        sys.exit(1)

    # Server must bind to 0.0.0.0 according to Section 2.1
    server = GameServer(host="0.0.0.0", port=args.port)
    server.start()


if __name__ == "__main__":
    main()
