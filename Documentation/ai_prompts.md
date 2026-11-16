# AI Assistant Rules & Prompting Constraints

This document defines the strict rules, architectural boundaries, and prompting constraints that the AI coding assistant must adhere to during the implementation of the CS 457 networked game project.

---

## 1. Sprint 1: Application-Layer Protocol & FSM Adherence Rules

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
- `STATE_UPDATE` (Server -> Clients: payload contains `board`, `scores`, `active_player`, `seq`)
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
- **0-Byte EOF Detection:** Socket `recv()` loops must explicitly evaluate `if not data: break` to detect graceful disconnects and prevent CPU-spinning loops.
- **Graceful Shutdown:** Clean disconnects must follow the application `DISCONNECT` message and TCP FIN handshake (`socket.shutdown(socket.SHUT_WR)` followed by `socket.close()`).
- **Abrupt Disconnection Handling:** Catch `ConnectionResetError`, `BrokenPipeError`, `ConnectionAbortedError`, and `socket.timeout` gracefully without crashing the server or orphan client threads.

---

## 2. Sprint 2: Concurrency, Locking & Synchronization Rules

The AI coding assistant must strictly align all concurrency and locking logic with [`sequenceDiagram.md`](./sequenceDiagram.md) and [`concurrency_design.md`](./concurrency_design.md):

### 2.1 Server Concurrency Strategy
- **Non-blocking Multiplexing:** Server uses non-blocking I/O multiplexing (`selectors.DefaultSelector` or `select.select`).
- **Lock Discipline:** Shared game state mutations must be protected using `threading.Lock()` wrapped in Python's `with self.state_lock:` context manager.
- **Rule of Lock Release:** The server must **always release the lock before dispatching network broadcasts (`sock.sendall()`)**. Slow or stalled clients must never hold the game lock or block other players.

### 2.2 Sequence Tracking & Snapshotting
- **Deep-Copy Snapshotting:** State snapshots (`copy.deepcopy(board)`) must be taken inside the critical section before serialization.
- **Monotonic Sequence (`seq`):** Incremented on every `STATE_UPDATE`. Clients discard arriving frames where `seq <= last_seq` to prevent out-of-order jitter.

---

## 3. Sprint 3: Code Implementation & Technical Requirements

Sprint 3 implements `src/server.py` and `src/client.py` fulfilling the following specifications:

### 3.1 CLI Argument Parsing
- **Client (`client.py`):**
  - `-h`: Displays help instructions.
  - `-i`, `--hostname`: Server DNS hostname (required; resolved via `socket.gethostbyname()`).
  - `-p`, `--port`: Server port (required).
  - `-u`, `--username`: Optional player username.
- **Server (`server.py`):**
  - `-h`: Displays help instructions.
  - `-p`, `--port`: Listening port (required; binds to `0.0.0.0`).

### 3.2 Graceful DNS Resolution Exception Handling (Mandatory)
The client must catch `socket.gaierror` explicitly, fail gracefully with non-zero exit code 1, and output user-friendly diagnostic guidance without raw tracebacks:
```python
try:
    server_ip = socket.gethostbyname(args.hostname)
except socket.gaierror as e:
    print(f"[ERROR] Unable to resolve DNS hostname '{args.hostname}'.")
    print("Please check your Cisco router DNS configuration ('ip dns server' / 'ip host') or verify domain spelling.")
    sys.exit(1)
```

### 3.3 Network Transport & Socket Implementation
- Sockets created with `socket.socket(socket.AF_INET, socket.SOCK_STREAM)`.
- Server binds to `0.0.0.0` with `SO_REUSEADDR`.
- Newline-delimited JSON frame buffering and parsing on both client and server.

### 3.4 CLI User Interface
- Clear ASCII grid displaying current board state alongside 1-9 cell reference keys.
- Real-time turn prompts ("YOUR TURN (X)" vs "Waiting for opponent...").
- Full score summaries and game over results.

---

## 4. Modular AI System Prompts for Code Generation

### Prompt 1: Strict Protocol Framing & Accumulator
```text
You are an expert Python network engineer implementing the networking layer for CS 457.
You MUST adhere strictly to the following constraints:
1. Transport: Raw TCP stream sockets (socket.SOCK_STREAM).
2. Serialization: JSON.
3. Framing: Every message is newline-delimited ('\n').
4. Implement a robust buffer accumulator in the receive loop:
   - Read data in chunks (sock.recv(1024)).
   - Check 'if not data: break' (0-byte EOF detection) to prevent infinite 100% CPU loops.
   - Buffer chunks and split on '\n' to yield complete JSON objects.
   - Retain partial messages in the accumulator for the next recv() cycle.
5. Catch ConnectionResetError, BrokenPipeError, ConnectionAbortedError, and TimeoutError gracefully.
```

### Prompt 2: DNS Resolution & CLI Arguments
```text
Implement CLI argument parsing and network resolution for CS 457 client.py:
1. Parse -h, -i/--hostname (required), -p/--port (required, int), -u/--username.
2. Resolve hostname using socket.gethostbyname(hostname).
3. MUST wrap in try/except socket.gaierror:
   print error message advising user to check router DNS ('ip dns server' / 'ip host') and call sys.exit(1).
   Never allow raw tracebacks to escape.
```

### Prompt 3: Server Concurrency & Non-Blocking Multiplexing
```text
Implement the server concurrency architecture for the CS 457 Tic-Tac-Toe server.
Requirements:
1. Use Python's standard library 'selectors' module for non-blocking I/O multiplexing.
2. Register the listening server socket with DefaultSelector for EVENT_READ bound to 0.0.0.0.
3. Register accepted client sockets as non-blocking (setblocking(False)).
4. Enclose state mutations in 'with self.state_lock:'.
5. Release state_lock BEFORE broadcasting STATE_UPDATE frames over client sockets.
```
