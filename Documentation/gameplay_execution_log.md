# CS 457 Sprint 3 - Intermediate Gameplay Execution Log

**Course:** CS 457 - Computer Networks  
**Student:** Jacob Zier  
**Deliverable:** Sprint 3 Intermediate Gameplay Execution Log  
**Configuration:** Authoritative Server (`server.py -p 19879`), Client 1 (`Alice` / `Player_1` / Mark `X`), Client 2 (`Bob` / `Player_2` / Mark `O`).  
**Result:** 5 successive turns of gameplay executed successfully across raw TCP sockets with newline-delimited JSON framing, ending in victory for Player 1 (3-in-a-row diagonal).

---

## 1. Server Console Execution Log (`server.py -p 19879`)

```text
[2026-11-15 18:08:00] [INFO] Tic-Tac-Toe Server started. Listening on 0.0.0.0:19879 (non-blocking I/O multiplexing)
[2026-11-15 18:08:01] [INFO] Accepted connection from ('127.0.0.1', 40310), assigned: Player_1
[2026-11-15 18:08:01] [INFO] Received [CONNECT] from Player_1
[2026-11-15 18:08:01] [INFO] Sent LOBBY_WAIT to Player_1
[2026-11-15 18:08:02] [INFO] Accepted connection from ('127.0.0.1', 40312), assigned: Player_2
[2026-11-15 18:08:02] [INFO] Received [CONNECT] from Player_2
[2026-11-15 18:08:02] [INFO] FSM: WaitingForPlayers -> GameActive -> PlayerXTurn (seq=1)
[2026-11-15 18:08:03] [INFO] Received [MOVE] from Player_1
[2026-11-15 18:08:03] [INFO] FSM: Valid move [0, 0] by Player_1. Next: Player_2 (O), seq=2
[2026-11-15 18:08:04] [INFO] Received [MOVE] from Player_2
[2026-11-15 18:08:04] [INFO] FSM: Valid move [0, 1] by Player_2. Next: Player_1 (X), seq=3
[2026-11-15 18:08:05] [INFO] Received [MOVE] from Player_1
[2026-11-15 18:08:05] [INFO] FSM: Valid move [1, 1] by Player_1. Next: Player_2 (O), seq=4
[2026-11-15 18:08:06] [INFO] Received [MOVE] from Player_2
[2026-11-15 18:08:06] [INFO] FSM: Valid move [0, 2] by Player_2. Next: Player_1 (X), seq=5
[2026-11-15 18:08:07] [INFO] Received [MOVE] from Player_1
[2026-11-15 18:08:07] [INFO] FSM: Move committed -> XWins (Player_1 wins!)
[2026-11-15 18:08:07] [INFO] FSM: Game ended -> Terminated
[2026-11-15 18:08:07] [INFO] Received 0-byte EOF from Player_1 (('127.0.0.1', 40310)). Remote closed connection.
[2026-11-15 18:08:07] [INFO] Socket closed for Player_1.
[2026-11-15 18:08:07] [INFO] Received 0-byte EOF from Player_2 (('127.0.0.1', 40312)). Remote closed connection.
[2026-11-15 18:08:07] [INFO] Socket closed for Player_2.
[2026-11-15 18:08:07] [INFO] All clients disconnected. Resetting game room to WaitingForPlayers.
```

---

## 2. Client 1 (Player 1 / Alice - Mark 'X') Console Log

```text
[INFO] Resolved 'localhost' -> 127.0.0.1
[INFO] Connecting to game server at 127.0.0.1:19879...
[INFO] Successfully connected to localhost (127.0.0.1:19879)

[LOBBY] In queue as Player_1. Waiting for Player_2 to join...

==================================================
               GAME START!
==================================================
  * Player_1 (Alice): Role X
  * Player_2 (Bob): Role O

Starting Player: Player_1
You are: Player_1 (Mark: 'X')
==================================================

      Current Board:                Cell Key (1-9):
        0   1   2
     0  - | - | -                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | - | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | -                   7 | 8 | 9

Scores: Player_1: 0 | Player_2: 0  [Frame seq=1]

>>> YOUR TURN (X) <<<
Enter move for 'X' (row col [0-2], key [1-9], or 'quit'): 
      Current Board:                Cell Key (1-9):
        0   1   2
     0  X | - | -                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | - | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | -                   7 | 8 | 9

Scores: Player_1: 0 | Player_2: 0  [Frame seq=2]

>>> Waiting for opponent (Player_2 / 'O')... <<<

      Current Board:                Cell Key (1-9):
        0   1   2
     0  X | O | -                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | - | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | -                   7 | 8 | 9

Scores: Player_1: 0 | Player_2: 0  [Frame seq=3]

>>> YOUR TURN (X) <<<
Enter move for 'X' (row col [0-2], key [1-9], or 'quit'): 
      Current Board:                Cell Key (1-9):
        0   1   2
     0  X | O | -                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | X | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | -                   7 | 8 | 9

Scores: Player_1: 0 | Player_2: 0  [Frame seq=4]

>>> Waiting for opponent (Player_2 / 'O')... <<<

      Current Board:                Cell Key (1-9):
        0   1   2
     0  X | O | O                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | X | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | -                   7 | 8 | 9

Scores: Player_1: 0 | Player_2: 0  [Frame seq=5]

>>> YOUR TURN (X) <<<
Enter move for 'X' (row col [0-2], key [1-9], or 'quit'): 
      Current Board:                Cell Key (1-9):
        0   1   2
     0  X | O | O                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | X | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | X                   7 | 8 | 9


**************************************************
                  GAME OVER
**************************************************
Result: Player_1_Wins
Winner: Player_1 ('X')
Final Scores: Player_1: 1 | Player_2: 0
**************************************************

[INFO] Client connection closed.
```

---

## 3. Client 2 (Player 2 / Bob - Mark 'O') Console Log

```text
[INFO] Resolved 'localhost' -> 127.0.0.1
[INFO] Connecting to game server at 127.0.0.1:19879...
[INFO] Successfully connected to localhost (127.0.0.1:19879)

==================================================
               GAME START!
==================================================
  * Player_1 (Alice): Role X
  * Player_2 (Bob): Role O

Starting Player: Player_1
You are: Player_2 (Mark: 'O')
==================================================

      Current Board:                Cell Key (1-9):
        0   1   2
     0  - | - | -                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | - | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | -                   7 | 8 | 9

Scores: Player_1: 0 | Player_2: 0  [Frame seq=1]

>>> Waiting for opponent (Player_1 / 'X')... <<<

      Current Board:                Cell Key (1-9):
        0   1   2
     0  X | - | -                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | - | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | -                   7 | 8 | 9

Scores: Player_1: 0 | Player_2: 0  [Frame seq=2]

>>> YOUR TURN (O) <<<
Enter move for 'O' (row col [0-2], key [1-9], or 'quit'): 
      Current Board:                Cell Key (1-9):
        0   1   2
     0  X | O | -                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | - | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | -                   7 | 8 | 9

Scores: Player_1: 0 | Player_2: 0  [Frame seq=3]

>>> Waiting for opponent (Player_1 / 'X')... <<<

      Current Board:                Cell Key (1-9):
        0   1   2
     0  X | O | -                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | X | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | -                   7 | 8 | 9

Scores: Player_1: 0 | Player_2: 0  [Frame seq=4]

>>> YOUR TURN (O) <<<
Enter move for 'O' (row col [0-2], key [1-9], or 'quit'): 
      Current Board:                Cell Key (1-9):
        0   1   2
     0  X | O | O                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | X | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | -                   7 | 8 | 9

Scores: Player_1: 0 | Player_2: 0  [Frame seq=5]

>>> Waiting for opponent (Player_1 / 'X')... <<<

      Current Board:                Cell Key (1-9):
        0   1   2
     0  X | O | O                   1 | 2 | 3
       ---+---+---                 ---+---+---
     1  - | X | -                   4 | 5 | 6
       ---+---+---                 ---+---+---
     2  - | - | X                   7 | 8 | 9


**************************************************
                  GAME OVER
**************************************************
Result: Player_1_Wins
Winner: Player_1 ('X')
Final Scores: Player_1: 1 | Player_2: 0
**************************************************

[INFO] Client connection closed.
```
