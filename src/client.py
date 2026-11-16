#!/usr/bin/env python3
"""CS 457 Tic-Tac-Toe Game Client (Sprint 3 Deliverable).

Author: Jacob Zier
Course: CS 457 - Computer Networks

This module implements the networked Tic-Tac-Toe client.
It parses CLI arguments, performs DNS resolution with graceful exception handling,
connects over a raw TCP socket, sends and receives newline-delimited JSON frames,
enforces sequence number anti-jitter, and renders a clean CLI interface.

Usage:
    python3 client.py -h
    python3 client.py -i <hostname> -p <port>
    python3 client.py -i server.zier.edu -p 8080
"""

import argparse
import json
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# Protocol Blueprint Constants (Sprint 1)
# ============================================================================
MSG_CONNECT = "CONNECT"
MSG_LOBBY_WAIT = "LOBBY_WAIT"
MSG_GAME_START = "GAME_START"
MSG_MOVE = "MOVE"
MSG_STATE_UPDATE = "STATE_UPDATE"
MSG_GAME_OVER = "GAME_OVER"
MSG_DISCONNECT = "DISCONNECT"
MSG_ERROR = "ERROR"


# ============================================================================
# Board Rendering & Input Parsing
# ============================================================================
def render_board(board: List[List[str]]) -> str:
    """Renders a clean human-readable CLI game board with coordinate reference."""
    b = board
    lines = [
        "",
        "      Current Board:                Cell Key (1-9):",
        "        0   1   2",
        f"     0  {b[0][0]} | {b[0][1]} | {b[0][2]}                   1 | 2 | 3",
        "       ---+---+---                 ---+---+---",
        f"     1  {b[1][0]} | {b[1][1]} | {b[1][2]}                   4 | 5 | 6",
        "       ---+---+---                 ---+---+---",
        f"     2  {b[2][0]} | {b[2][1]} | {b[2][2]}                   7 | 8 | 9",
        ""
    ]
    return "\n".join(lines)


def parse_move_input(user_input: str) -> Tuple[Optional[int], Optional[int]]:
    """Parses move input as either row and col ('0 2' or '0,2') or cell key (1-9).

    Returns:
        (row, col) or (None, None) if invalid.
    """
    clean_input = user_input.replace(",", " ").strip()
    parts = clean_input.split()

    # Form 1: "row col" (e.g. "0 2")
    if len(parts) == 2:
        try:
            r = int(parts[0])
            c = int(parts[1])
            if 0 <= r <= 2 and 0 <= c <= 2:
                return r, c
        except ValueError:
            return None, None

    # Form 2: 1-9 single cell number
    if len(parts) == 1:
        try:
            val = int(parts[0])
            if 1 <= val <= 9:
                idx = val - 1
                return idx // 3, idx % 3
        except ValueError:
            return None, None

    return None, None


# ============================================================================
# Client Application & Network Receiver
# ============================================================================
class GameClient:
    """Manages the client network socket, background receiver, and game loop."""

    def __init__(self, hostname: str, port: int, username: str):
        self.hostname = hostname
        self.port = port
        self.username = username

        self.sock: Optional[socket.socket] = None
        self.server_ip: Optional[str] = None

        # Game state tracking
        self.my_player_id = username        # e.g., "Player_1", assigned by server
        self.my_role: Optional[str] = None  # "X" or "O"
        self.last_seq = 0                   # Anti-jitter sequence filter
        self.board: List[List[str]] = [
            ["-", "-", "-"],
            ["-", "-", "-"],
            ["-", "-", "-"]
        ]

        # Thread synchronization events
        self.my_turn_event = threading.Event()
        self.game_over_event = threading.Event()
        self.running = True

    def connect_to_server(self) -> None:
        """Resolves DNS hostname and connects to server via TCP socket."""
        # --------------------------------------------------------------------
        # 2.2 Graceful DNS Resolution Exception Handling (Mandatory Requirement)
        # --------------------------------------------------------------------
        try:
            self.server_ip = socket.gethostbyname(self.hostname)
        except socket.gaierror as e:
            print(f"[ERROR] Unable to resolve DNS hostname '{self.hostname}'.")
            print("Please check your Cisco router DNS configuration ('ip dns server' / 'ip host') or verify domain spelling.")
            sys.exit(1)

        print(f"[INFO] Resolved '{self.hostname}' -> {self.server_ip}")
        print(f"[INFO] Connecting to game server at {self.server_ip}:{self.port}...")

        # --------------------------------------------------------------------
        # 2.3 Network Transport Socket Connection
        # --------------------------------------------------------------------
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.server_ip, self.port))
            print(f"[INFO] Successfully connected to {self.hostname} ({self.server_ip}:{self.port})")
        except (ConnectionRefusedError, socket.error, OSError) as e:
            print(f"[ERROR] Failed to establish TCP connection to {self.server_ip}:{self.port} - {e}")
            print("Ensure the server is running and reachable on this port.")
            sys.exit(1)

    def send_framed_message(self, msg_dict: Dict[str, Any]) -> bool:
        """Encodes dictionary as newline-delimited JSON and transmits over TCP."""
        if not self.sock:
            return False
        try:
            data = (json.dumps(msg_dict) + "\n").encode("utf-8")
            self.sock.sendall(data)
            return True
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError) as e:
            print(f"\n[NETWORK ERROR] Connection lost while transmitting: {e}")
            self.running = False
            self.game_over_event.set()
            return False

    def receiver_loop(self) -> None:
        """Background thread receiving and processing newline-delimited server frames."""
        recv_buffer = ""

        while self.running and not self.game_over_event.is_set():
            try:
                chunk = self.sock.recv(1024)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError) as e:
                if self.running and not self.game_over_event.is_set():
                    print(f"\n[NETWORK WARNING] Server connection interrupted: {e}")
                break

            # 2.4.3 Handling the TCP 0-Byte EOF Condition
            if not chunk:
                if not self.game_over_event.is_set():
                    print("\n[INFO] Remote server closed connection (EOF received).")
                break

            recv_buffer += chunk.decode("utf-8", errors="replace")

            while "\n" in recv_buffer:
                line, recv_buffer = recv_buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                self._handle_server_frame(line)

        self.running = False
        self.game_over_event.set()
        self.my_turn_event.set()  # Unblock main thread if waiting

    def _handle_server_frame(self, raw_line: str) -> None:
        """Dispatches an incoming JSON message from the server."""
        try:
            msg = json.loads(raw_line)
        except json.JSONDecodeError as err:
            print(f"[WARN] Failed to decode server frame: {err}")
            return

        msg_type = msg.get("msg_type")
        payload = msg.get("payload", {})

        if msg_type == MSG_LOBBY_WAIT:
            your_id = payload.get("your_player_id")
            if your_id:
                self.my_player_id = your_id
            waiting_for = payload.get("waiting_for", "Player 2")
            print(f"\n[LOBBY] In queue as {self.my_player_id}. Waiting for {waiting_for} to join...")

        elif msg_type == MSG_GAME_START:
            your_id = payload.get("your_player_id")
            your_role = payload.get("your_role")
            if your_id:
                self.my_player_id = your_id
            if your_role:
                self.my_role = your_role

            player_roles = payload.get("player_roles", {})
            player_names = payload.get("player_names", {})
            starting_player = payload.get("starting_player", "Player_1")

            # Fallback if not explicitly set
            if not self.my_role:
                for pid, role in player_roles.items():
                    name = player_names.get(pid, pid)
                    if name == self.username or pid == self.username:
                        self.my_player_id = pid
                        self.my_role = role
                        break

            print("\n" + "=" * 50)
            print(" " * 15 + "GAME START!")
            print("=" * 50)
            for pid, role in player_roles.items():
                pname = player_names.get(pid, pid)
                print(f"  * {pid} ({pname}): Role {role}")
            print(f"\nStarting Player: {starting_player}")
            if self.my_role:
                print(f"You are: {self.my_player_id} (Mark: '{self.my_role}')")
            print("=" * 50)

        elif msg_type == MSG_STATE_UPDATE:
            seq = payload.get("seq", 0)
            # Anti-jitter sequence validation (Sprint 2 Requirement)
            if seq <= self.last_seq and self.last_seq != 0:
                # Discard stale or duplicate packet
                return
            self.last_seq = seq

            self.board = payload.get("board", self.board)
            active_player = payload.get("active_player", "")
            active_role = payload.get("active_role", "")
            scores = payload.get("scores", {})

            # Render updated board
            print(render_board(self.board))
            if scores:
                scores_str = " | ".join(f"{p}: {s}" for p, s in scores.items())
                print(f"Scores: {scores_str}  [Frame seq={seq}]")

            # Check turn entitlement
            is_my_turn = (active_player == self.my_player_id or active_role == self.my_role)
            if is_my_turn:
                print(f"\n>>> YOUR TURN ({self.my_role}) <<<")
                self.my_turn_event.set()
            else:
                print(f"\n>>> Waiting for opponent ({active_player} / '{active_role}')... <<<")
                self.my_turn_event.clear()

        elif msg_type == MSG_ERROR:
            err_code = payload.get("error_code", "UNKNOWN")
            err_msg = payload.get("error_message", "An error occurred.")
            print(f"\n[SERVER REJECTION] {err_code}: {err_msg}")
            # Re-enable input if it was rejected during our turn
            self.my_turn_event.set()

        elif msg_type == MSG_GAME_OVER:
            result = payload.get("result", "Game Ended")
            final_board = payload.get("final_board")
            winner = payload.get("winner", "None")
            winner_symbol = payload.get("winner_symbol")
            reason = payload.get("reason")
            scores = payload.get("scores", {})

            if final_board:
                print(render_board(final_board))

            print("\n" + "*" * 50)
            print(" " * 18 + "GAME OVER")
            print("*" * 50)
            print(f"Result: {result}")
            if winner and winner != "None":
                symbol_str = f" ('{winner_symbol}')" if winner_symbol else ""
                print(f"Winner: {winner}{symbol_str}")
            else:
                print("Outcome: Draw / Tie game!")
            if reason:
                print(f"Notice: {reason}")
            if scores:
                scores_str = " | ".join(f"{p}: {s}" for p, s in scores.items())
                print(f"Final Scores: {scores_str}")
            print("*" * 50 + "\n")

            self.game_over_event.set()
            self.my_turn_event.set()

    def run(self) -> None:
        """Starts client network connection, receiver thread, and input loop."""
        self.connect_to_server()

        # Send initial application CONNECT handshake (Section 2.2 schema)
        connect_packet = {
            "msg_type": MSG_CONNECT,
            "player_id": self.username,
            "timestamp": int(time.time())
        }
        self.send_framed_message(connect_packet)

        # Launch background receiver thread for non-blocking stream listening
        receiver = threading.Thread(target=self.receiver_loop, daemon=True)
        receiver.start()

        # Interactive gameplay loop in main thread
        try:
            while self.running and not self.game_over_event.is_set():
                # Wait for server to signal it is our turn
                self.my_turn_event.wait(timeout=0.5)

                if self.game_over_event.is_set() or not self.running:
                    break

                if not self.my_turn_event.is_set():
                    continue

                # Prompt user for move input
                try:
                    prompt = f"Enter move for '{self.my_role}' (row col [0-2], key [1-9], or 'quit'): "
                    user_cmd = input(prompt).strip()
                except (EOFError, KeyboardInterrupt):
                    user_cmd = "quit"

                if not user_cmd:
                    continue

                if user_cmd.lower() in ("quit", "exit", "q"):
                    print("\n[INFO] Quitting game. Sending DISCONNECT to server...")
                    disconnect_packet = {
                        "msg_type": MSG_DISCONNECT,
                        "player_id": self.my_player_id,
                        "timestamp": int(time.time())
                    }
                    self.send_framed_message(disconnect_packet)
                    break

                # Parse row, col
                row, col = parse_move_input(user_cmd)
                if row is None or col is None:
                    print("[INPUT ERROR] Invalid format! Please enter 'row col' (e.g. '0 2') or 1-9.")
                    continue

                # Clear event while waiting for server validation
                self.my_turn_event.clear()

                # Dispatch MOVE intent (Section 2.2 schema)
                move_packet = {
                    "msg_type": MSG_MOVE,
                    "player_id": self.my_player_id,
                    "payload": {
                        "row": row,
                        "col": col
                    },
                    "timestamp": int(time.time())
                }
                self.send_framed_message(move_packet)

        except KeyboardInterrupt:
            print("\n[INFO] Session interrupted by user (Ctrl+C). Exiting...")
            if self.sock:
                disconnect_packet = {
                    "msg_type": MSG_DISCONNECT,
                    "player_id": self.my_player_id,
                    "timestamp": int(time.time())
                }
                self.send_framed_message(disconnect_packet)
        finally:
            self._teardown()

    def _teardown(self) -> None:
        """Orderly socket shutdown and resource cleanup."""
        self.running = False
        self.game_over_event.set()
        if self.sock:
            try:
                # 2.4.1 Transport-Level TCP FIN Teardown
                self.sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
        print("[INFO] Client connection closed.")


# ============================================================================
# CLI Argument Parser (30 Points)
# ============================================================================
def parse_arguments() -> argparse.Namespace:
    """Parses command line arguments according to Section 2.1."""
    parser = argparse.ArgumentParser(
        description="CS 457 Tic-Tac-Toe Game Client (Sprint 3)"
    )
    parser.add_argument(
        "-i", "--hostname",
        type=str,
        required=True,
        help="Server DNS hostname (e.g. server.zier.edu or localhost)"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        required=True,
        help="Server port"
    )
    parser.add_argument(
        "-u", "--username",
        type=str,
        default="Player",
        help="Optional player username / player ID (default: 'Player')"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    # Port range validation
    if not (1 <= args.port <= 65535):
        print(f"[ERROR] Port {args.port} is invalid. Port must be between 1 and 65535.")
        sys.exit(1)

    client = GameClient(
        hostname=args.hostname,
        port=args.port,
        username=args.username
    )
    client.run()


if __name__ == "__main__":
    main()
