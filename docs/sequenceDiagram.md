```mermaid
---
config:
  theme: mc
---
sequenceDiagram
    autonumber
    actor ClientO as Client (Player O)
    participant Server as Server (Authoritative)
    actor ClientX as Client (Player X)

    %% Out-of-turn rejection scenario
    rect rgb(255, 240, 240)
        note over ClientO, ClientX: Invalid Action: Player O moves during Player X's turn
        ClientO->>+Server: MOVE_INTENT(player_id="O", row=1, col=1)
        critical Acquire state_lock
            Server->>Server: Validate: game_over == False
            Server->>Server: Validate: current_turn == "X"
            Server-->>Server: Check failed: "O" != "X" (Out-of-turn)
        end
        Server-->>-ClientO: ACTION_REJECTED(code="ERR_OUT_OF_TURN", msg="It is Player X's turn")
    end

    %% Valid move and broadcast scenario
    rect rgb(240, 255, 240)
        note over ClientO, ClientX: Valid Action: Player X executes move
        ClientX->>+Server: MOVE_INTENT(player_id="X", row=0, col=2)
        critical Acquire state_lock
            Server->>Server: Validate: current_turn == "X" (Match)
            Server->>Server: Validate: cell (0, 2) is empty
            Server->>Server: Mutate board: board[0][2] = "X"
            Server->>Server: Toggle turn: current_turn = "O"
            Server->>Server: Take snapshot of board & scores
        end

        note over Server: Release state_lock before I/O broadcast
        
        par Authoritative Full-State Broadcast
            Server->>ClientX: STATE_UPDATE(board, scores, active_turn="O", seq=1)
        and
            Server->>-ClientO: STATE_UPDATE(board, scores, active_turn="O", seq=1)
        end
    end

    Note over ClientO: Enable cell inputs (My turn)<br/>Update grid canvas & scoreboard
    Note over ClientX: Disable cell inputs (Waiting)<br/>Update grid canvas & scoreboard