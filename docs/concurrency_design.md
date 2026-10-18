## 3. Game Behavior & Server Concurrency Architecture (Sprint 2 Deliverable)

### 3.1 Server Concurrency Strategy
- **Architecture Choice:** Non-blocking I/O multiplexing (`select.select` / `selectors`)
- **Synchronization Logic:** When a move occurs, a server will update move through the two clients and update the board, to prevent a lock there will be a mutual exlusion lock, python's "with" statement guarentees that a lock can be acquired before entering the block and a lock will be released no matter what.

### 3.2 State & Score Synchronization Across Clients
- **Turn Enforcement:** The sevver will be in charge of game progression, determining whose turn it is and approve and validate the client actions. A thread will get the clients ID and the cordinates of the move. Once those are vcalidated, the server will commit the move to the board and change the turn. Then the server will broadcast the updated board and whose turn it is across all open sockets
- **Score & Board Synchronization:** The server will create a deep copy of the game so that client inputs can't change the payload while it is serializing into a JSON message which is then sent across the thread of all the active clients. there will be a move history count that acts as a sequence ID, if a packet arrives with a sequence ID lower than the user's current sequence, the frame is discarded, preventing packets from jittering the interace. 

---