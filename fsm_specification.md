---
config:
  fontFamily: '''Inter Variable'', sans-serif'
  look: classic
  theme: dark
  themeVariables:
    fontFamily: '''Inter Variable'', sans-serif'
---
stateDiagram
  direction TB
  [*] --> WaitingForPlayers
  WaitingForPlayers --> GameActive:Both players joined
  WaitingForPlayers --> Terminated:Server shutdown
  GameActive --> PlayerXTurn:Game initialized
  PlayerXTurn --> PlayerOTurn:Valid move by X
  PlayerXTurn --> InvalidMove:Invalid move attempted
  PlayerXTurn --> OWins:X leaves or disconnects
  PlayerOTurn --> PlayerXTurn:Valid move by O
  PlayerOTurn --> InvalidMove:Invalid move attempted
  PlayerOTurn --> XWins:O leaves or disconnects
  InvalidMove --> PlayerXTurn:X turn (after invalid)
  InvalidMove --> PlayerOTurn:O turn (after invalid)
  PlayerXTurn --> XWins:X achieved 3-in-a-row
  PlayerOTurn --> OWins:O achieved 3-in-a-row
  PlayerXTurn --> Draw:Board full, no winner
  PlayerOTurn --> Draw:Board full, no winner
  XWins --> Terminated:Game ended
  OWins --> Terminated:Game ended
  Draw --> Terminated:Game ended
  Terminated --> [*]