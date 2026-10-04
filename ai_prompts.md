# AI Assistant Rules & Prompting Constraints

This document defines the strict rules, architectural boundaries, and prompting constraints that the AI coding assistant must adhere to during the implementation of the CS 457 networked game project.

---

## 1. Core Architectural & Protocol Adherence Rules

The AI coding assistant must strictly align all generated code, logic, and tests with the designs specified in [`protocol_blueprint.md`](./protocol_blueprint.md) and [`fsm_specification.md`](./fsm_specification.md).

### 1.1 Transport, Serialization & Framing Constraints
- **Transport Layer:** Must use raw TCP stream sockets (`socket.SOCK_STREAM`).
- **Serialization Format:** Must use valid JSON encoding (`json.dumps()`, `json.loads()`).
- **Message Framing:** Every message must be newline-delimited (`\n`). 
  - Socket read loops must correctly buffer incoming chunks and split by `\n` to prevent packet coalescing/fragmentation issues.
  - Back-to-back messages must be properly parsed without data loss.

### 1.2 Message Schema Compliance
All messages sent between Client and Server must adhere strictly to the schemas defined in Section 2.2 of `protocol_blueprint.md`:
- `CONNECT` (Client -> Server)
- `LOBBY_WAIT` (Server -> Client)
- `GAME_START` (Server -> Clients)
- `MOVE` (Client -> Server: payload contains `{"row": int, "col": int}`)
- `STATE_UPDATE` (Server -> Clients: payload contains `board` 3x3 and `active_player`)
- `GAME_OVER` (Server -> Clients: payload contains `result`, `final_board`, `winner`)
- `DISCONNECT` (Client -> Server)
- `ERROR` (Server -> Client: payload contains `error_code`, `error_message`)

### 1.3 Finite State Machine (FSM) Enforcement
All state management on the server must strictly implement the states and transitions defined in `fsm_specification.md`:
- **States:** `WaitingForPlayers`, `GameActive`, `PlayerXTurn`, `PlayerOTurn`, `InvalidMove`, `XWins`, `OWins`, `Draw`, `Terminated`.
- **Transitions:**
  - Moves alternate strictly between Player X and Player O.
  - Out-of-turn or occupied-cell moves transition to `InvalidMove`, return an `ERROR` message (`OUT_OF_TURN` or `INVALID_CELL`), and return turn to the current player without modifying the board.
  - Disconnect during a player's turn immediately awards victory to the remaining player and transitions to `Terminated`.
  - Win condition: 3-in-a-row (row, column, or diagonal).
  - Draw condition: all 9 cells filled with no winner.

### 1.4 Socket Lifecycle & Error Handling Constraints
- **0-Byte EOF Detection:** Socket `recv()` loops must explicitly evaluate `if not data:` to detect graceful disconnects and prevent CPU-spinning loops.
- **Graceful Shutdown:** Clean disconnects must follow the application `DISCONNECT` message and TCP FIN handshake (`socket.shutdown(socket.SHUT_WR)` followed by `socket.close()`).
- **Abrupt Disconnection Handling:** Catch `ConnectionResetError`, `BrokenPipeError`, `ConnectionAbortedError`, and `socket.timeout` gracefully without crashing the server or orphan client threads.

---
