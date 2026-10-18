## 2. Application-Layer Messaging Protocol Blueprint (Sprint 1 Deliverable)

### 2.1 Message Transport & Serialization Format
- **Transport Protocol:** TCP
- **Serialization Format:** JSON
- **Framing Mechanism:** Newline-delimited (`\n`)
- **Example Back-to-Back Byte Stream:**
  ```text
  {"msg_type":"CONNECT","player_id":"Player_1","timestamp":1727000000}\n{"msg_type":"MOVE","player_id":"Player_1","payload":{"row":0,"col":2},"timestamp":1727000005}\n
  ```

### 2.2 Message Schema Definitions

#### Message Types:
1. `CONNECT` (Client -> Server): Request to join the game room.
2. `LOBBY_WAIT` (Server -> Client): Notification that server is waiting for Player 2.
3. `GAME_START` (Server -> Clients): Game initiated, assigns roles (e.g. Player X vs Player O).
4. `MOVE` (Client -> Server): Player action (e.g., cell coordinates or answer choice).
5. `STATE_UPDATE` (Server -> Clients): Broadcast current game board / state and active player turn.
6. `GAME_OVER` (Server -> Clients): Victory / Draw notification with final scores.
8. `DISCONNECT` (Client -> Server): Client notifies server of intentional depature/quit
7. `ERROR` (Server -> Client): Invalid move or malformed packet error.

```json
{
  "msg_type": "CONNECT",
  "player_id": "Player_1",
  "timestamp": 1727000000
}

{
  "msg_type": "LOBBY_WAIT",
  "player_id": "SERVER",
  "payload": {
    "waiting_for": "Player_2"
  },
  "timestamp": 1727000001
}

{
  "msg_type": "GAME_START",
  "player_id": "SERVER",
  "payload": {
    "player_roles": {
      "Alice": "Player_1",
      "Bob": "Player_2"
    },
    "starting_player": "Player_1"
  },
  "timestamp": 1727000002
}

{
  "msg_type": "MOVE",
  "player_id": "Player_1",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000005
}

{
  "msg_type": "STATE_UPDATE",
  "player_id": "SERVER",
  "payload": {
    "board": [
      ["X", "-", "-"],
      ["-", "O", "-"],
      ["-", "-", "-"]
    ],
    "active_player": "Player_2"
  },
  "timestamp": 1727000006
}

{
  "msg_type": "ERROR",
  "player_id": "SERVER",
  "payload": {
    "error_code": "OUT_OF_TURN",
    "error_message": "It is not your turn."
  },
  "timestamp": 1727000007
}

{
  "msg_type": "DISCONNECT",
  "player_id": "Player_1",
  "timestamp": 1727000010
}

{
  "msg_type": "GAME_OVER",
  "player_id": "SERVER",
  "payload": {
    "result": "Player_1_Wins",
    "final_board": [
      ["X", "X", "X"],
      ["O", "-", "-"],
      ["O", "-", "-"]
    ],
    "winner": "Player_1"
  },
  "timestamp": 1727000020
}
```

---

### 2.3 Game State Machine (FSM) Design (Sprint 1 Deliverable)
- **State Transitions:** See fsm_specifications.md

---

### 2.4 Connection Termination & Socket Lifecycle Management

In a production networked application, connections terminate both gracefully (intentional player exit) and abnormally (crashes, cable pulls, network drops). Your protocol and state machine must explicitly handle connection termination.

#### 1. Transport-Layer Termination vs. Application Disconnection:
- **Application-Layer Disconnect (`DISCONNECT` Message):** An active client sends a structured `DISCONNECT` or `QUIT` message before terminating. This allows the server to notify the opponent cleanly, declare a win by forfeit, and immediately reclaim resources.
- **Transport-Layer Teardown (TCP FIN / Clean Closure):** When a process calls `sock.close()` or exits normally, the operating system initiates the TCP 4-way FIN handshake.
- **Abrupt Termination (TCP RST / Hard Drops):** If a client process is killed abruptly (`kill -9`, power loss, or a severed router link in CML), no FIN handshake is completed. The next attempt to read or write will trigger a TCP Reset (RST) or timeout.

#### 2. The TCP EOF (0-Byte) Rule in Socket Programming:
When a remote host closes its socket connection cleanly, calling `recv()` on that socket does not raise an exception. Instead, `recv()` returns 0 bytes (`b""` in Python, `0` in C).

- **Critical Socket Rule:** A return value of `b""` represents EOF (End-Of-File). It is the POSIX standard indicator that the remote peer closed the write-half of the connection.
- **Infinite Loop Danger:** If your socket receive loop does not check `if not data: break`, your application will enter an infinite loop consuming 100% CPU because `recv()` will immediately return `b""` on every subsequent call.

```python
# Standard pattern for detecting TCP connection termination:
data = sock.recv(1024)
if not data:
    # Remote peer closed connection cleanly (TCP FIN received)
    logger.info("Remote peer disconnected (EOF received).")
    sock.close()
    handle_client_disconnect(player_id)
```

#### 3. Handling Socket Exceptions During Network Drops:
When network links fail or clients crash, low-level socket operations raise exceptions:
- **`ConnectionResetError` (TCP RST):** The peer host forcibly closed the connection or crashed.
- **`BrokenPipeError` (EPIPE):** Occurs when your application attempts to `sock.send()` or `sendall()` to a socket whose remote end is already closed.
- **`TimeoutError`:** Occurs if a socket timeout is configured and the peer stops responding.
A message dispatch loops must catch these exceptions to trigger state machine cleanup and prevent process crashes:

```python
try:
    data = recv_exact(sock, msg_len)
    if data is None:
        trigger_state_transition("CLIENT_DISCONNECTED")
except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
    logger.warning(f"Connection lost abruptly: {e}")
    trigger_state_transition("CLIENT_DISCONNECTED")
```