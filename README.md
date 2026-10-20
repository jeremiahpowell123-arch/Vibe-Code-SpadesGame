# Spades

A desktop Spades card game written in Python with [pygame-ce](https://github.com/pygame-community/pygame-ce). You and a computer partner (North) play against two computer opponents (West and East) on a green felt table, with a main menu, adjustable difficulty, 250- or 500-point matches, ten card styles, and a scrollable history of every round you have played.

The game is a single file with no image assets required. Everything on screen (cards, suits, trophy, card backs) is drawn in code.

> **Built with Claude.** The code was written in conversation with Claude (Anthropic). See [How this was built with Claude](#how-this-was-built-with-claude) for what I asked for, what changed along the way, and what went wrong and got fixed.

## Features

- **Full 4-player Spades.** Fixed partnerships (You + North vs. West + East), bidding, Nil bids, spades as trump, follow-suit rules, bags, and the 10-bag penalty.
- **Everyone bids their own hand.** Each player bids for the cards they hold. Team bids are the sum of the two partners' bids.
- **Rotating first bidder.** The player who bids first also leads first, and that seat moves clockwise every hand (You, West, North, East).
- **Clear bidding.** The player whose turn it is to bid glows, every bid stays highlighted until the round starts, and a "Bids are in" panel shows each team's total before play begins.
- **Smart computer players.** Three difficulty levels, set separately for your partner and for the opponents. Computer players recognize a Nil bid: opponents try to bust it, and partners cover it.
- **Main menu and options.** New Game, Resume, Options, Match History, Quit.
- **Two match lengths.** Play to 250 or 500.
- **Ten card styles.** Five colors (Classic Blue, Ruby Red, Emerald, Royal Purple, Midnight Gold) and five holidays (Halloween, Christmas, Valentine's Day, Fourth of July, St. Patrick's Day).
- **Match history.** A scrollable table of every round: each player's bid and tricks taken, round points, running score, bags gained, and total bags.
- **Match-over celebration.** An animated "YOU WIN!" screen with a trophy and confetti, or "Better Luck Next Time" with a card fan and drifting suits.
- **Spades are grayed out until you can play them,** along with any other card you are not allowed to play right now.

## Getting started

### Requirements

- Python 3 (developed on macOS with Python 3.15)
- [pygame-ce](https://pypi.org/project/pygame-ce/) (developed and tested with 2.5.8)

I recommend `pygame-ce` rather than the original `pygame` package. On a very new Python version, the original package may have no prebuilt wheel and fail to install, while `pygame-ce` usually publishes wheels sooner. You still write `import pygame`. The game was tested with `pygame-ce` only.

### Install and run

```bash
git clone https://github.com/jeremiahpowell123-arch/Vibe-Code-SpadesGame.git
cd Vibe-Code-SpadesGame

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install pygame-ce

python3 main.py
```

### Running from PyCharm

1. Open the project folder.
2. Make sure the project interpreter is the project's `.venv` (Settings, then Project, then Python Interpreter).
3. Install `pygame-ce` from that same screen (the **+** button), or run `pip install pygame-ce` in PyCharm's Terminal tab while the prompt shows `(.venv)`.
4. Run `main.py`.

> **Common pitfall:** each PyCharm project has its own `.venv`. Installing pygame-ce with the system `pip3` does not make it available inside the project, and you will see `ModuleNotFoundError: No module named 'pygame'`. Install it into the interpreter the project actually uses.

## How to play

**Teams and seating.** You (South) and North are partners against West and East. Play goes clockwise: You, West, North, East.

**Bidding.** Each player bids how many tricks their own hand will take, from 1 to 13, or **Nil** (0) to try to take no tricks. A team's contract is the total of its partners' non-Nil bids.

**Playing a hand.**
- You must follow the suit led if you can.
- Spades are trump. A spade beats any card of another suit, and the highest spade wins.
- You cannot lead a spade until spades have been "broken" (a spade has been played), unless your hand is all spades. If you cannot follow suit, you may play a spade, which breaks spades.
- Cards you cannot play right now are grayed out. Clicking one explains why.

**Scoring.**

| Situation | Points |
|---|---|
| Team makes its contract | +10 per bid trick, plus +1 for each extra trick ("bag") |
| Team is set (takes fewer tricks than bid) | -10 per bid trick |
| Nil made (that player takes no tricks) | +100 |
| Nil failed | -100 |
| Every 10 bags collected | -100, and the bag count drops by 10 |

A failed Nil bidder's tricks still count toward the team's total.

**Winning.** The match ends when a team reaches the target score (250 or 500) and the scores are not tied. If both teams reach it in the same hand, the higher score wins. If they are tied, play continues.

**Not implemented:** blind Nil, and the optional rule that ends the match when a team falls to -200.

### Controls

| Action | How |
|---|---|
| Bid | Click a number button (or Nil) |
| Play a card | Click a card in your hand (a playable card lifts when you hover over it) |
| Start the round after bidding | Click anywhere once the "Bids are in" panel appears |
| Continue after a hand | Click anywhere |
| Menu / History | Buttons at the bottom-left and bottom-right of the table |
| Go back | `Esc` returns to the previous screen (the table goes to the menu) |
| Scroll history | Mouse wheel, arrow keys, Page Up/Down, Home/End, or click the scrollbar |

## Options

Open **Options** from the main menu.

| Setting | Choices | Applies |
|---|---|---|
| Your partner (North) | Easy, Medium, Hard | Next new game |
| Opponents (West and East) | Easy, Medium, Hard | Next new game |
| Play to | 250, 500 | Next new game |
| Card style | 10 styles | Immediately |

### Using your own card images (optional)

Create a folder named `cards` next to `main.py` and add images named by rank and suit:

```
cards/
  AS.jpg  KH.jpg  QD.jpg  10C.jpg  2S.jpg  ...
  back.jpg
```

Ranks are `2` to `10`, `J`, `Q`, `K`, `A`, and suits are `S`, `H`, `D`, `C`. `.jpg`, `.jpeg`, and `.png` all work. A **My Images** style then appears in Options. Images are scaled to 90 by 130 pixels, so use that proportion, and keep the rank and suit in the top-left corner because cards in your hand overlap. Any image that is missing is drawn in code instead.

### Saved data

The game creates `spades_save.json` next to the script. It stores your options and your last 25 finished matches, and it is read again on the next launch. A missing or damaged file is ignored and the game starts fresh. Add `spades_save.json` to your `.gitignore` if you do not want your personal history committed.

## How the computer players work

| Level | Behavior |
|---|---|
| **Easy** | Plays the same quick rules as Medium, but picks a random legal card 40% of the time, and its bids are deliberately noisy. |
| **Medium** | Rule-based play. Follows sensible habits (win cheaply, do not waste a card when its partner is already winning), and recognizes Nil bids: it covers a partner's Nil and tries to bust an opponent's. It has no memory of the cards played. |
| **Hard** | Remembers every card played and which suits each player has shown they are out of. For each decision it imagines many possible deals of the unseen cards, tries every legal card by playing out the rest of the hand, and picks the card that gives its team the best expected score. That score includes contracts, setting the other team, Nil bids, bags, and the 10-bag penalty. This is why Hard players push to set a team that has overbid, avoid collecting extra bags when close to the penalty, and lead suits where a Nil bidder is likely to be forced high. |

All three levels bid using the same hand-strength estimate (high cards and spade length). Easy adds random error to it.

In a head-to-head simulation of 150 identical deals, a Hard West/East pair beat a Medium You/North pair by about 30 points per hand (plus or minus 12), compared with about 6 (plus or minus 13) when both pairs were Medium. The Hard pair set the other team in 31% of hands, versus 22% when both were Medium. Easy has not been benchmarked the same way.

## Project layout

```
.
├── main.py             # the entire game
├── cards/              # optional: your own card images
├── spades_save.json    # created automatically (options + match history)
└── README.md
```

`main.py` is organized into labeled sections, top to bottom: settings, cards, rules, bots, scoring, game state, layout, card styles, drawing, match-over screen, menu and options, match history, the `App` that ties the screens together, and the main loop.

Useful constants near the top of the file:

| Constant | Meaning |
|---|---|
| `WIDTH`, `HEIGHT` | Window size (1100 by 800) |
| `CARD_W`, `CARD_H` | Card size in pixels |
| `BOT_DELAY_MS` | Pause before a computer player plays a card |
| `BID_DELAY_MS` | Pause before a computer player bids |
| `TRICK_PAUSE_MS` | How long a finished trick stays on the table |
| `BOT_SAMPLES` | How many possible deals a Hard player imagines per decision (higher is sharper but slower) |
| `BAG_LIMIT` | Bags that trigger the penalty |

## How this was built with Claude

I built this project as a conversation with Claude, starting from a Pygame tutorial I could not get running and ending with a complete game. I described what I wanted, played the result, and reported what felt wrong. Claude wrote and revised the code, explained each change, and tested it. Here is how it went.

### Getting set up

- **Python basics along the way.** I asked short questions (operators, `elif`, making input case-insensitive) while learning.
- **Installing Pygame.** `pip install pygame` failed on Python 3.15 because no prebuilt wheel existed, so pip tried to compile it. Claude suggested `pygame-ce`, which installed cleanly.
- **A virtual environment mix-up.** The package then still "was not found" in PyCharm because I had installed it with the system `pip3`, while PyCharm runs the project's own `.venv`. We fixed it by installing into the project's environment. The same thing happened again with the new Spades project, and Claude's first answer ("your venv already has pygame-ce") was wrong because each project has its own.

### Warm-up: Space Dodge

Before Spades I followed a Space Dodge tutorial. When the window never appeared, Claude found the cause: `main()` and the start-up block were indented inside another function, so nothing ever called them. I asked Claude to walk through each change one by one, then to give me line numbers for every edit. I kept asking for line numbers in later instructions, and it made the changes much easier to apply. Claude then offered two ways to replace the red rectangle with a spaceship: shapes drawn in code, or an image file.

### The Spades game

1. **A text version first.** Claude wrote a console Spades game and ran 40 full simulated games to make sure it never crashed and always finished.
2. **A Pygame window.** I asked for a window with a green table and, if I added card pictures, to use them. Claude asked what images I had. I had none yet, so the cards are drawn in code and my own `.jpg` files can be dropped in later.
3. **Playtesting and revisions.** After that, almost every change came from playing the game and telling Claude what was wrong:

| What I noticed or asked for | What changed |
|---|---|
| The bid prompt asked how many tricks "you and North" would take, but I cannot see North's hand. | Everyone now bids for their own hand. The team bid is the sum, and the results screen shows the split (for example "You 3 + North 2"). |
| The first bidder should rotate each hand. | The rotation was already correct. I had misjudged it because the bots bid so fast that I could not follow along. Claude confirmed it by simulating ten hands, made every game start with me bidding first, and added a glowing name tag for the bidder, highlighted bids that stay until the round starts, a pause between bids, and a "Bids are in" summary panel. |
| If I bid Nil, the opponents should play low, and my partner should cover me (and the same for West and East). | Claude noticed the two sides need opposite behavior (opponents duck low, partners cover high) and added both for every seat, with unit tests for each situation. |
| Opponents should lead suits where I am likely to be forced high. | Bots gained memory (cards played, suits each player is out of) and started imagining possible deals to test each card. |
| They should always play skillfully, for example setting us when the table bids close to 13, and avoiding bags when they already have many. | The bots stopped using special-case rules and began scoring every possible play by the full points result of the hand. Those behaviors then came out of the same calculation. |
| Menu, options (difficulty, 250 or 500, ten card styles), in-game access to a history page, a better match-over screen, and no more "Spades not broken" text. | The large update described in the Features section: an `App` layer with menu, options, history, and celebration screens, saved settings and history, and graying out spades until they are playable. |
| Valentine's Day cards use hearts, which is confusing because Hearts is a suit. I suggested a teddy bear. | Replaced with a teddy bear on the card back and in two corners of every face. Claude had already removed suit-shaped icons from the faces of Midnight Gold and Valentine's Day after reviewing a contact sheet of all ten styles, but the heart on the Valentine's card back was still there until I pointed it out. |

### Mistakes that were caught and fixed

Not everything Claude wrote was right the first time, and the project is better for catching these:

- **A wrong instruction.** When adding a spaceship image, Claude first said to put the loading line before `PLAYER_WIDTH` and `PLAYER_HEIGHT` were defined, which would crash with a `NameError`. Claude corrected it as soon as I asked for line numbers.
- **A misleading prompt.** The "you and North" bid text described a rule the code did not actually use. The behavior was right and the wording was wrong.
- **A crash a test found.** Claude's tests deliberately fed the game damaged and hand-edited save files. One incomplete match record would have crashed the History page. Saved matches are now validated and bad ones are dropped on load.
- **A confusing design.** Suit-shaped icons on card faces looked fine on paper and wrong on a contact sheet of all ten styles.

### How the code was tested

Claude tested by running the game without a window and driving it with scripted clicks, plus screenshots that we both reviewed. Checks included:

- Whole matches played through the real click paths, at both 250 and 500 points, with every round's tricks, running scores, bags, and penalties verified.
- The menu, options, history scrolling, and match-over buttons.
- Spade-graying rules for leading, following, being out of a suit, and spades being broken.
- Settings and history surviving a restart, and damaged save files being ignored safely.
- Simulations that compared the old computer players with the new ones before changes were accepted.

I verified the game by playing it myself and reporting what felt off.

### What I took away

- **Describe the behavior you want, not just the symptom.** "Opponents should play low and my partner should cover" produced better results than "make Nil work."
- **Paste the exact error.** Almost every setup problem was solved from the real traceback.
- **Ask for line numbers and step-by-step explanations.** It makes changes easy to follow and apply.
- **Playtest.** Simulations are good at finding crashes and measuring strength. They are bad at noticing that bidding goes by too fast to follow.
- **Expect to correct the assistant.** Several of the best improvements came from me pushing back.

## Ideas for the future

- Blind Nil
- A stronger bidding strategy for the computer players (bidding is still a simple hand-strength estimate)
- Sound effects
