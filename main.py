"""Spades - pygame version.

You (South) and North are partners against West and East.
Pick New Game from the menu, click a bid button, then click a card to play it.
Options (difficulty, 250 or 500 points, 10 card styles) are saved in
spades_save.json next to this file, together with your match history.

Optional card images: make a folder named "cards" next to this file and put
jpg (or png) files in it named like  AS.jpg  KH.jpg  10D.jpg  2C.jpg  back.jpg
(rank 2-10, J, Q, K, A + suit letter S, H, D, C). A "My Images" style then
appears in Options. Any image that is missing is drawn in code instead.
"""
import json
import math
import os
import random
import time

import pygame

# ----------------------------- Settings -----------------------------
WIDTH, HEIGHT = 1100, 800
FPS = 60
BAG_LIMIT = 10            # every 10 overtricks ("bags") costs 100 points
CARD_W, CARD_H = 90, 130  # card size on screen (your images get scaled to this)
BOT_DELAY_MS = 800        # pause before each bot plays a card
BID_DELAY_MS = 1500       # pause before each bot bids, so you can follow the bidding
TRICK_PAUSE_MS = 1500     # how long a finished trick stays on the table
BOT_SAMPLES = 80          # bot skill: how many possible deals a bot imagines per decision (more = sharper, slower)
TABLE_GREEN = (22, 112, 62)
CARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cards")

# ----------------------------- Cards --------------------------------
SPADES, HEARTS, DIAMONDS, CLUBS = "S", "H", "D", "C"
SUIT_ORDER = [SPADES, HEARTS, CLUBS, DIAMONDS]
SUIT_NAMES = {"S": "spades", "H": "hearts", "D": "diamonds", "C": "clubs"}
SUIT_COLORS = {"S": (20, 20, 20), "C": (20, 20, 20),
               "H": (200, 20, 30), "D": (200, 20, 30)}
RANK_NAMES = {11: "J", 12: "Q", 13: "K", 14: "A"}

# Seats go clockwise: 0 (You) -> 1 (West) -> 2 (North) -> 3 (East).
SEAT_NAMES = ["You", "West", "North", "East"]
TEAM_NAMES = ["Your team", "Opponents"]


def rank_label(value):
    return RANK_NAMES.get(value, str(value))


def make_deck():
    return [(suit, value) for suit in SUIT_ORDER for value in range(2, 15)]


def sort_hand(hand):
    hand.sort(key=lambda c: (SUIT_ORDER.index(c[0]), -c[1]))


# ----------------------------- Rules --------------------------------
def legal_plays(hand, lead_suit, spades_broken):
    """Return the cards from hand that may be played right now."""
    if lead_suit is None:  # leading the trick
        if spades_broken:
            return list(hand)
        non_spades = [c for c in hand if c[0] != SPADES]
        return non_spades if non_spades else list(hand)
    follow = [c for c in hand if c[0] == lead_suit]
    return follow if follow else list(hand)


def beats(card, best):
    """Does card beat the card currently winning the trick?"""
    if card[0] == best[0]:
        return card[1] > best[1]
    return card[0] == SPADES  # a spade trumps any other suit


def current_winner(trick):
    best_seat, best_card = trick[0]
    for seat, card in trick[1:]:
        if beats(card, best_card):
            best_seat, best_card = seat, card
    return best_seat, best_card


# ----------------------------- Bots ---------------------------------
def estimate_bid(hand):
    spades = [c[1] for c in hand if c[0] == SPADES]
    n_spades = len(spades)
    est = 0
    if 14 in spades:
        est += 1
    if 13 in spades and n_spades >= 2:
        est += 1
    if 12 in spades and n_spades >= 3:
        est += 1
    if n_spades > 3:
        est += n_spades - 3  # long spades take extra tricks
    for suit in (HEARTS, DIAMONDS, CLUBS):
        values = [c[1] for c in hand if c[0] == suit]
        if 14 in values:
            est += 1
        if 13 in values and len(values) >= 2:
            est += 1
        if not values and n_spades >= 3:
            est += 1  # void suit: can trump in
    return est


def bot_bid(hand, level="Medium"):
    est = estimate_bid(hand)
    if level == "Easy":  # Easy bots misjudge their hands
        est = max(0, est + random.choice([-2, -1, 0, 0, 1, 2]))
    if est == 0:
        highest = max(c[1] for c in hand)
        return 0 if highest <= 10 else 1  # 0 = Nil
    return min(est, 13)


def pick_high(cards):
    """Highest card, saving spades if a non-spade will do."""
    non_spades = [c for c in cards if c[0] != SPADES]
    return max(non_spades or cards, key=lambda c: c[1])


def lowest_card(cards):
    """Lowest card, keeping spades for last."""
    return min(cards, key=lambda c: (c[0] == SPADES, c[1]))


def simple_play(seat, hand, trick, spades_broken, bids, tricks_won, bags=(0, 0)):
    """Quick rule-based play. Also used to imagine how everyone else will play."""
    lead_suit = trick[0][1][0] if trick else None
    legal = legal_plays(hand, lead_suit, spades_broken)
    if len(legal) == 1:
        return legal[0]

    cheapest = lowest_card(legal)
    partner = (seat + 2) % 4
    played = [s for s, _ in trick]
    win_seat, win_card = current_winner(trick) if trick else (None, None)

    # Who is still going for Nil? (bid Nil and has not taken a trick yet)
    nil_alive = [s for s in range(4) if bids[s] == 0 and tricks_won[s] == 0]

    # --- My own Nil: stay under the winning card ---
    if seat in nil_alive:
        if not trick:
            return cheapest
        losing = [c for c in legal if not beats(c, win_card)]
        if losing:
            return max(losing, key=lambda c: c[1])
        return cheapest

    # --- My partner is going for Nil: cover them ---
    if partner in nil_alive:
        if not trick:
            return pick_high(legal)  # lead high so partner can duck under it
        if partner not in played:
            # Partner plays after me: set a high card for them to duck under.
            winners = [c for c in legal if beats(c, win_card)]
            return pick_high(winners) if winners else cheapest
        if win_seat == partner:
            # Partner's card is currently winning: beat it with the cheapest winner.
            winners = [c for c in legal if beats(c, win_card)]
            return lowest_card(winners) if winners else cheapest
        # Partner is already safe: play normally below.

    # --- Contract situation for my team and the other team ---
    team, other = seat % 2, 1 - seat % 2
    my_contract = sum(bids[s] for s in (team, team + 2) if bids[s] > 0)
    opp_contract = sum(bids[s] for s in (other, other + 2) if bids[s] > 0)
    my_tricks = tricks_won[team] + tricks_won[team + 2]
    opp_tricks = tricks_won[other] + tricks_won[other + 2]
    my_need = my_contract - my_tricks
    opp_need = opp_contract - opp_tricks

    # --- An opponent is going for Nil: try to force them to win a trick ---
    opp_nils = [s for s in nil_alive if (s - seat) % 2 == 1]
    if opp_nils and partner not in nil_alive:
        for nil_seat in opp_nils:
            if nil_seat in played and win_seat == nil_seat:
                # Their card is winning: do NOT take it away from them.
                losing = [c for c in legal if not beats(c, win_card)]
                return lowest_card(losing) if losing else cheapest
        if any(s not in played for s in opp_nils) and my_need <= 0:
            # They have yet to play: keep the winning card low, so they may be
            # forced to go over it.
            return cheapest

    # --- Normal play: do I actually want more tricks? ---
    bag_danger = my_contract > 0 and bags[team] + max(0, my_tricks + 1 - my_contract) >= BAG_LIMIT
    if my_need > 0:
        want_win = True
    elif opp_need > 0:
        want_win = not bag_danger  # extra tricks can set the opponents
    else:
        want_win = False           # nothing to gain from more tricks

    if not want_win:
        # Give tricks away (avoids bags) while getting rid of high cards.
        if not trick or win_seat == partner:
            return cheapest
        losing = [c for c in legal if not beats(c, win_card)]
        return max(losing, key=lambda c: c[1]) if losing else cheapest

    if not trick:
        aces = [c for c in legal if c[1] == 14 and c[0] != SPADES]
        if aces:
            return aces[0]
        if all(c[0] == SPADES for c in legal):
            return max(legal, key=lambda c: c[1])
        return cheapest

    if win_seat == partner:  # partner is winning, don't waste a card
        return cheapest

    winners = [c for c in legal if beats(c, win_card)]
    if winners:
        return lowest_card(winners)
    return cheapest


# ---- Skilled play: imagine many possible deals and test every card ----
def distinct_choices(legal, hand, played):
    """Drop cards that are equivalent (touching ranks in the same suit)."""
    keep = []
    by_suit = {}
    for c in legal:
        by_suit.setdefault(c[0], []).append(c)
    for suit, cards in by_suit.items():
        cards.sort(key=lambda c: c[1])
        known = {v for s, v in played if s == suit} | {c[1] for c in hand if c[0] == suit}
        keep.append(cards[0])
        for prev, cur in zip(cards, cards[1:]):
            if not all(v in known for v in range(prev[1] + 1, cur[1])):
                keep.append(cur)
    return keep


def sample_deals(seat, hand, info, nil_seats, k):
    """Imagine k possible deals of the unseen cards among the other three seats.

    Uses only public information: cards already played, which suits a player has
    shown they are out of, and how many cards each player still holds. A player
    who bid Nil is assumed to hold mostly low cards.
    """
    others = [s for s in range(4) if s != seat]
    unseen = [c for c in make_deck() if c not in info["played"] and c not in hand]
    capacity = {s: info["sizes"][s] for s in others}
    if sum(capacity.values()) != len(unseen):
        return []
    deals, attempts = [], 0
    while len(deals) < k and attempts < k * 8:
        attempts += 1
        cap = dict(capacity)
        hands = {s: [] for s in others}
        cards = unseen[:]
        random.shuffle(cards)
        # place the most restricted cards first (suits some player is out of)
        cards.sort(key=lambda c: sum(c[0] in info["voids"][s] for s in others), reverse=True)
        ok = True
        for c in cards:
            options = [s for s in others if cap[s] > 0 and c[0] not in info["voids"][s]]
            if not options:
                ok = False
                break
            weights = [cap[s] * ((15 - c[1]) / 12 if s in nil_seats else 1.0) for s in options]
            chosen = random.choices(options, weights)[0]
            hands[chosen].append(c)
            cap[chosen] -= 1
        if ok:
            deals.append(hands)
    return deals


def finish_hand_quickly(seat, card, deal, my_hand, trick, spades_broken, bids, tricks_won, bags):
    """Play out the rest of the hand with simple_play; return tricks won per seat."""
    hands = {s: list(h) for s, h in deal.items()}
    hands[seat] = [c for c in my_hand if c != card]
    won = list(tricks_won)
    t = trick + [(seat, card)]
    broken = spades_broken or card[0] == SPADES
    while True:
        while len(t) < 4:
            nxt = (t[-1][0] + 1) % 4
            if not hands[nxt]:
                return won
            c = simple_play(nxt, hands[nxt], t, broken, bids, won, bags)
            hands[nxt].remove(c)
            t.append((nxt, c))
            if c[0] == SPADES:
                broken = True
        winner = current_winner(t)[0]
        won[winner] += 1
        if not hands[winner]:
            return won
        c = simple_play(winner, hands[winner], [], broken, bids, won, bags)
        hands[winner].remove(c)
        broken = broken or c[0] == SPADES
        t = [(winner, c)]


def smart_play(seat, hand, legal, trick, spades_broken, bids, tricks_won, info):
    """Choose the card that scores best for my team over many imagined deals.

    Every candidate is tested by playing the rest of the hand and counting points
    (contracts, setting the other team, Nil, bags and the bag penalty). That makes
    the bots set a team that overbid, avoid sandbagging when close to the penalty,
    bust and cover Nils, and so on, without a special rule for each.
    """
    candidates = distinct_choices(legal, hand, info["played"])
    if len(candidates) == 1:
        return candidates[0]
    nil_alive = [s for s in range(4) if bids[s] == 0 and tricks_won[s] == 0]
    # Think less when there are many cards to test, to keep the game snappy.
    k = max(8, min(BOT_SAMPLES, 36000 // (len(candidates) * len(hand) * 4)))
    deals = sample_deals(seat, hand, info, nil_alive, k)
    if not deals:
        return None
    bags = info.get("bags", [0, 0])
    team = seat % 2
    best_card, best_score = None, None
    for card in candidates:
        total = 0
        for deal in deals:
            won = finish_hand_quickly(seat, card, deal, hand, trick, spades_broken,
                                      bids, tricks_won, bags)
            mine = team_hand_result(team, bids, won, bags[team])[0]
            theirs = team_hand_result(1 - team, bids, won, bags[1 - team])[0]
            total += mine - theirs
        score = total / len(deals) - 0.04 * (card[1] + (13 if card[0] == SPADES else 0))
        if best_score is None or score > best_score:
            best_card, best_score = card, score
    return best_card


def bot_play(seat, hand, trick, spades_broken, bids, tricks_won, info=None):
    """Pick a card. With info (cards played, who is out of which suit) the bot plays
    skillfully; without it, it falls back to the quick rules."""
    lead_suit = trick[0][1][0] if trick else None
    legal = legal_plays(hand, lead_suit, spades_broken)
    if len(legal) == 1:
        return legal[0]
    own_nil = bids[seat] == 0 and tricks_won[seat] == 0
    if info is not None and not own_nil:
        card = smart_play(seat, hand, legal, trick, spades_broken, bids, tricks_won, info)
        if card is not None:
            return card
    return simple_play(seat, hand, trick, spades_broken, bids, tricks_won,
                       info.get("bags", (0, 0)) if info else (0, 0))


# ----------------------------- Scoring ------------------------------
def bid_text(bid):
    if bid is None:
        return "-"
    return "Nil" if bid == 0 else str(bid)


def team_hand_result(team, bids, tricks_won, bags_before, notes=None):
    """What a team scores this hand. Returns (points, bags_after).

    Pass a list as notes to have the explanation lines appended to it."""
    seats = (team, team + 2)
    contract = sum(bids[s] for s in seats if bids[s] > 0)
    team_tricks = tricks_won[seats[0]] + tricks_won[seats[1]]
    points, bags_after = 0, bags_before

    if contract > 0:
        if team_tricks >= contract:
            over = team_tricks - contract
            points += 10 * contract + over
            bags_after += over
            if notes is not None:
                # e.g. "You 3 + North 4": each player's own bid, added into the team bid
                split = " + ".join(f"{SEAT_NAMES[s]} {bids[s]}" for s in seats if bids[s] > 0)
                notes.append(f"made {contract} ({split}), +{over} bag(s)")
            if bags_after >= BAG_LIMIT:
                bags_after -= BAG_LIMIT
                points -= 100
                if notes is not None:
                    notes.append("bag penalty -100")
        else:
            points -= 10 * contract
            if notes is not None:
                split = " + ".join(f"{SEAT_NAMES[s]} {bids[s]}" for s in seats if bids[s] > 0)
                notes.append(f"set: bid {contract} ({split}), took {team_tricks}")

    for s in seats:
        if bids[s] == 0:
            if tricks_won[s] == 0:
                points += 100
                if notes is not None:
                    notes.append(f"{SEAT_NAMES[s]} made Nil +100")
            else:
                points -= 100
                if notes is not None:
                    notes.append(f"{SEAT_NAMES[s]} failed Nil -100")
    return points, bags_after


def score_hand(bids, tricks_won, scores, bags):
    """Update scores and bags; return a list of text lines describing the hand."""
    lines = []
    for team in (0, 1):
        notes = []
        points, bags[team] = team_hand_result(team, bids, tricks_won, bags[team], notes)
        scores[team] += points
        lines.append(f"{TEAM_NAMES[team]}: {points:+d}   ({'; '.join(notes)})")
    return lines


# ----------------------------- Settings & saving --------------------
LEVELS = ["Easy", "Medium", "Hard"]
LEVEL_INFO = {
    "Easy": "Plays fast and makes plenty of mistakes",
    "Medium": "Solid, rule-based play",
    "Hard": "Remembers every card and plans ahead",
}
TARGETS = [250, 500]
DEFAULT_SETTINGS = {"partner": "Hard", "opponents": "Hard", "target": 250,
                    "style": "Classic Blue"}
EASY_MISTAKE_RATE = 0.4   # Easy bots play a random legal card this often
MAX_MATCHES = 25          # how many finished matches the history keeps
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spades_save.json")


def load_save():
    """Read saved settings and match history. Never raises: a missing or damaged
    file just means starting fresh."""
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_save(settings, matches):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump({"settings": settings, "matches": matches}, f)
    except OSError:
        pass  # saving is a convenience; the game keeps working without it


def _ints(seq, n):
    return (isinstance(seq, list) and len(seq) == n
            and all(isinstance(x, int) and not isinstance(x, bool) for x in seq))


def valid_round(r):
    return (isinstance(r, dict) and _ints(r.get("bids"), 4) and _ints(r.get("tricks"), 4)
            and _ints(r.get("points"), 2) and _ints(r.get("scores"), 2)
            and _ints(r.get("bags_gained"), 2) and _ints(r.get("bags"), 2)
            and isinstance(r.get("penalty"), list) and len(r["penalty"]) == 2)


def valid_match(m):
    """A saved match must be complete, or the history page could not draw it."""
    return (isinstance(m, dict) and m.get("winner") in (0, 1) and _ints(m.get("final"), 2)
            and isinstance(m.get("n", 0), int) and isinstance(m.get("rounds"), list)
            and all(valid_round(r) for r in m["rounds"]))


def choose_card(level, seat, hand, trick, spades_broken, bids, tricks_won, info):
    """Pick a card for a bot at the given difficulty level."""
    if level == "Hard":      # remembers cards, imagines deals, plans ahead
        return bot_play(seat, hand, trick, spades_broken, bids, tricks_won, info)
    if level == "Easy" and random.random() < EASY_MISTAKE_RATE:
        lead = trick[0][1][0] if trick else None
        return random.choice(legal_plays(hand, lead, spades_broken))
    return bot_play(seat, hand, trick, spades_broken, bids, tricks_won, None)  # quick rules


# ----------------------------- Game state ---------------------------
class Game:
    """Holds the state of one match. The window code only reads it and calls its methods."""

    def __init__(self, now=0, settings=None):
        s = dict(DEFAULT_SETTINGS)
        if settings:
            s.update(settings)
        self.settings = s
        self.target = s["target"]
        # Difficulty by seat: 0 = you (human), 1 = West, 2 = North (partner), 3 = East
        self.levels = {0: None, 1: s["opponents"], 2: s["partner"], 3: s["opponents"]}
        self.reset(now)

    def reset(self, now=0):
        """Start a fresh match with the same settings."""
        self.scores = [0, 0]
        self.bags = [0, 0]
        # East deals the first hand, so the player to East's left (You) bids and
        # leads first. After that the dealer moves one seat clockwise every hand,
        # so the first bidder goes You -> West -> North -> East -> You ...
        self.dealer = 3
        self.finished = False
        self.recorded = False   # has this finished match been saved to the history?
        self.rounds = []        # one record per hand, for the history page
        self.result_lines = []
        self.new_hand(now)

    def new_hand(self, now):
        deck = make_deck()
        random.shuffle(deck)
        self.hands = [deck[i * 13:(i + 1) * 13] for i in range(4)]
        for hand in self.hands:
            sort_hand(hand)
        self.bids = [None] * 4
        self.bid_order = [(self.dealer + 1 + i) % 4 for i in range(4)]
        self.bid_idx = 0
        self.tricks_won = [0] * 4
        self.spades_broken = False
        self.played = set()                   # every card played so far this hand
        self.voids = [set() for _ in range(4)]  # suits a player has shown they are out of
        self.leader = (self.dealer + 1) % 4
        self.turn = self.leader
        self.trick = []
        self.trick_winner = None
        self.phase = "bidding"  # bidding -> bids_review -> playing -> trick_done -> hand_over
        self.stamp = now
        self.flash_text = ""
        self.flash_until = 0

    # ---- helpers for drawing ----
    def actor(self):
        if self.phase == "bidding" and self.bid_idx < 4:
            return self.bid_order[self.bid_idx]
        if self.phase == "playing":
            return self.turn
        return None

    def human_must_bid(self):
        return (self.phase == "bidding" and self.bid_idx < 4
                and self.bid_order[self.bid_idx] == 0)

    def human_must_play(self):
        return self.phase == "playing" and self.turn == 0

    def hint_legal(self):
        """The cards you could play right now (used to gray out the rest).

        Spades stay grayed until they are allowed. None means nothing is grayed
        (for example while bidding)."""
        if self.phase == "playing":
            you_played = any(s == 0 for s, _ in self.trick)
            lead = self.trick[0][1][0] if self.trick and not you_played else None
            return legal_plays(self.hands[0], lead, self.spades_broken)
        if self.phase == "trick_done":
            return legal_plays(self.hands[0], None, self.spades_broken)
        return None

    def status_text(self):
        if self.phase == "bidding":
            if self.bid_idx >= 4 or self.bid_order[self.bid_idx] == 0:
                return ""
            return f"{SEAT_NAMES[self.bid_order[self.bid_idx]]} is bidding..."
        if self.phase == "playing":
            if self.turn == 0:
                return "Your turn - click a card to play"
            return f"{SEAT_NAMES[self.turn]} is thinking..."
        if self.phase == "trick_done":
            w = self.trick_winner
            return "You win the trick!" if w == 0 else f"{SEAT_NAMES[w]} wins the trick"
        return ""

    def trick_number(self):
        return min(13, sum(self.tricks_won) + 1)

    def winner(self):
        return 0 if self.scores[0] > self.scores[1] else 1

    # ---- actions ----
    def choose_bid(self, value, now):
        self.bids[0] = value
        self.bid_idx += 1
        self.stamp = now

    def try_play(self, index, now):
        hand = self.hands[0]
        lead = self.trick[0][1][0] if self.trick else None
        legal = legal_plays(hand, lead, self.spades_broken)
        card = hand[index]
        if card in legal:
            self.play_card(0, card, now)
        else:
            if lead is not None:
                self.flash_text = f"You must follow suit ({SUIT_NAMES[lead]})"
            else:
                self.flash_text = "Spades aren't broken yet - lead another suit"
            self.flash_until = now + 1800

    def play_card(self, seat, card, now):
        self.hands[seat].remove(card)
        if card[0] == SPADES:
            self.spades_broken = True
        if self.trick and card[0] != self.trick[0][1][0]:
            self.voids[seat].add(self.trick[0][1][0])  # didn't follow suit: out of it
        self.played.add(card)
        self.trick.append((seat, card))
        self.stamp = now
        if len(self.trick) == 4:
            self.trick_winner = current_winner(self.trick)[0]
            self.phase = "trick_done"
        else:
            self.turn = (seat + 1) % 4

    def finish_trick(self, now):
        winner = self.trick_winner
        self.tricks_won[winner] += 1
        self.leader = winner
        self.trick = []
        self.trick_winner = None
        if not any(self.hands):
            self.finish_hand(now)
        else:
            self.phase = "playing"
            self.turn = winner
            self.stamp = now

    def finish_hand(self, now):
        scores_before = list(self.scores)
        bags_before = list(self.bags)
        self.result_lines = score_hand(self.bids, self.tricks_won, self.scores, self.bags)
        gained, penalty = [], []
        for team in (0, 1):
            seats = (team, team + 2)
            contract = sum(self.bids[s] for s in seats if self.bids[s] > 0)
            took = self.tricks_won[seats[0]] + self.tricks_won[seats[1]]
            over = took - contract if contract > 0 and took >= contract else 0
            gained.append(over)
            penalty.append(bags_before[team] + over >= BAG_LIMIT)
        self.rounds.append({
            "bids": list(self.bids), "tricks": list(self.tricks_won),
            "points": [self.scores[t] - scores_before[t] for t in (0, 1)],
            "scores": list(self.scores),
            "bags_gained": gained, "bags": list(self.bags), "penalty": penalty,
        })
        self.finished = max(self.scores) >= self.target and self.scores[0] != self.scores[1]
        self.phase = "hand_over"
        self.stamp = now

    def match_record(self, number):
        return {"n": number, "when": time.strftime("%b %d, %Y  %I:%M %p"),
                "target": self.target, "partner": self.settings["partner"],
                "opponents": self.settings["opponents"], "final": list(self.scores),
                "winner": self.winner(), "rounds": self.rounds}

    # ---- input and timing ----
    def handle_click(self, pos, now):
        if self.phase == "bidding":
            if self.human_must_bid():
                for value, rect in enumerate(bid_button_rects()):
                    if rect.collidepoint(pos):
                        self.choose_bid(value, now)
                        return
        elif self.phase == "playing":
            if self.turn == 0:
                rects = hand_rects(len(self.hands[0]))
                for i in range(len(rects) - 1, -1, -1):  # topmost card first
                    if rects[i].collidepoint(pos):
                        self.try_play(i, now)
                        return
        elif self.phase == "bids_review":
            if now - self.stamp >= 300:  # everyone has bid: a click starts the round
                self.phase = "playing"
                self.turn = self.leader
                self.stamp = now
        elif self.phase == "hand_over":
            if self.finished:
                return                    # the match-over screen handles its own buttons
            if now - self.stamp < 400:  # ignore accidental double clicks
                return
            self.dealer = (self.dealer + 1) % 4
            self.new_hand(now)

    def update(self, now):
        if self.phase == "bidding":
            if self.bid_idx >= 4:
                self.phase = "bids_review"  # keep the bids on screen until you click
                self.stamp = now
                return
            seat = self.bid_order[self.bid_idx]
            if seat != 0 and now - self.stamp >= BID_DELAY_MS:
                self.bids[seat] = bot_bid(self.hands[seat], self.levels[seat])
                self.bid_idx += 1
                self.stamp = now
        elif self.phase == "playing":
            if self.turn != 0 and now - self.stamp >= BOT_DELAY_MS:
                seat = self.turn
                info = {"played": self.played, "voids": self.voids,
                        "sizes": [len(h) for h in self.hands], "bags": self.bags}
                card = choose_card(self.levels[seat], seat, self.hands[seat], self.trick,
                                   self.spades_broken, self.bids, self.tricks_won, info)
                self.play_card(seat, card, now)
        elif self.phase == "trick_done":
            if now - self.stamp >= TRICK_PAUSE_MS:
                self.finish_trick(now)


# ----------------------------- Layout -------------------------------
def hand_rects(n):
    """Rectangles for your cards, left to right (cards overlap a little)."""
    if n == 0:
        return []
    area = 900
    step = min(CARD_W + 12, (area - CARD_W) / (n - 1)) if n > 1 else 0
    total = step * (n - 1) + CARD_W
    x0 = (WIDTH - total) / 2
    y = HEIGHT - CARD_H - 30
    return [pygame.Rect(int(x0 + i * step), y, CARD_W, CARD_H) for i in range(n)]


def bid_button_rects():
    """14 buttons, index = bid value (0 is Nil)."""
    w, h, gap = 70, 50, 10
    x0 = (WIDTH - (7 * w + 6 * gap)) // 2
    rects = []
    for value in range(14):
        row, col = divmod(value, 7)
        rects.append(pygame.Rect(x0 + col * (w + gap), 330 + row * (h + gap), w, h))
    return rects


def trick_positions():
    cx, cy = WIDTH // 2, 380
    return {
        0: (cx - CARD_W // 2, cy + 10),
        1: (cx - CARD_W - 60, cy - CARD_H // 2),
        2: (cx - CARD_W // 2, cy - CARD_H - 10),
        3: (cx + 60, cy - CARD_H // 2),
    }


GAME_MENU_RECT = pygame.Rect(12, HEIGHT - 48, 84, 36)
GAME_HISTORY_RECT = pygame.Rect(WIDTH - 96, HEIGHT - 48, 84, 36)
BACK_RECT = pygame.Rect(30, 25, 120, 44)
HIST_VIEW = pygame.Rect(40, 130, 1020, 610)


def menu_items(resumable):
    items = []
    if resumable:
        items.append(("resume", "Resume Game"))
    items += [("new", "New Game"), ("options", "Options"),
              ("history", "Match History"), ("quit", "Quit")]
    return items


def menu_rects(items):
    w, h, gap = 340, 58, 16
    x = (WIDTH - w) // 2
    return [pygame.Rect(x, 290 + i * (h + gap), w, h) for i in range(len(items))]


def seg_rects(x, y, n, w=130, h=46, gap=12):
    return [pygame.Rect(x + i * (w + gap), y, w, h) for i in range(n)]


OPT_PARTNER_Y, OPT_OPP_Y, OPT_TARGET_Y = 110, 200, 290
OPT_SEG_X = 380
STYLE_CELL_W, STYLE_CELL_H, STYLE_GAP = 190, 170, 12


def style_cell_rects(count):
    cols = 5
    x0 = (WIDTH - (cols * STYLE_CELL_W + (cols - 1) * STYLE_GAP)) // 2
    rects = []
    for i in range(count):
        row, col = divmod(i, cols)
        rects.append(pygame.Rect(x0 + col * (STYLE_CELL_W + STYLE_GAP),
                                 398 + row * (STYLE_CELL_H + STYLE_GAP),
                                 STYLE_CELL_W, STYLE_CELL_H))
    return rects


def match_over_rects():
    w, h, gap = 230, 60, 20
    x0 = (WIDTH - (3 * w + 2 * gap)) // 2
    return [pygame.Rect(x0 + i * (w + gap), 650, w, h) for i in range(3)]


# ----------------------------- Card styles --------------------------
# Each style recolors the card faces and the card back. Holiday styles also put a
# small themed icon in two corners of every face and in a medallion on the back.
CARD_STYLES = [
    {"name": "Classic Blue", "back": (30, 60, 150), "accent": (200, 215, 255),
     "pattern": "diamonds", "face": (252, 252, 248), "edge": (50, 50, 50),
     "black": (20, 20, 20), "red": (200, 20, 30)},
    {"name": "Ruby Red", "back": (150, 20, 40), "accent": (255, 200, 205),
     "pattern": "diamonds", "face": (255, 250, 248), "edge": (80, 20, 25),
     "black": (30, 20, 20), "red": (200, 20, 30), "frame": True},
    {"name": "Emerald", "back": (10, 100, 70), "accent": (190, 240, 215),
     "pattern": "stripes", "face": (250, 253, 248), "edge": (10, 60, 40),
     "black": (15, 30, 25), "red": (200, 20, 30), "frame": True},
    {"name": "Royal Purple", "back": (80, 35, 140), "accent": (225, 205, 255),
     "pattern": "dots", "face": (252, 249, 255), "edge": (50, 20, 90),
     "black": (30, 20, 45), "red": (200, 20, 60), "frame": True},
    {"name": "Midnight Gold", "back": (18, 18, 30), "accent": (235, 190, 60),
     "pattern": "diamonds", "face": (250, 246, 232), "edge": (30, 25, 10),
     "black": (20, 20, 30), "red": (175, 30, 40), "frame": True,
     "motif": "spade", "motif_color": (18, 18, 30), "medal": (235, 190, 60),
     "trim": (235, 190, 60), "field": (30, 30, 48), "face_motif": False},
    {"name": "Halloween", "back": (235, 110, 10), "accent": (35, 20, 45),
     "pattern": "stripes", "face": (255, 243, 224), "edge": (60, 30, 0),
     "black": (40, 20, 50), "red": (205, 55, 10), "frame": True,
     "motif": "pumpkin", "motif_color": (240, 120, 10), "trim": (35, 20, 45)},
    {"name": "Christmas", "back": (160, 20, 30), "accent": (245, 250, 245),
     "pattern": "stripes", "face": (255, 252, 246), "edge": (20, 90, 50),
     "black": (10, 65, 38), "red": (190, 20, 30), "frame": True,
     "motif": "snowflake", "motif_color": (20, 100, 60), "trim": (245, 250, 245)},
    {"name": "Valentine's Day", "back": (225, 70, 125), "accent": (255, 225, 238),
     "pattern": "dots", "face": (255, 245, 248), "edge": (150, 30, 80),
     "black": (60, 25, 45), "red": (215, 30, 80), "frame": True,
     "motif": "teddy", "motif_color": (150, 95, 55), "trim": (255, 235, 242)},
    {"name": "Fourth of July", "back": (25, 50, 130), "accent": (240, 240, 250),
     "pattern": "vstripes", "face": (250, 250, 255), "edge": (25, 50, 130),
     "black": (20, 30, 70), "red": (200, 25, 40), "frame": True,
     "motif": "star", "motif_color": (200, 25, 40), "trim": (200, 25, 40)},
    {"name": "St. Patrick's Day", "back": (20, 130, 60), "accent": (250, 215, 70),
     "pattern": "checks", "face": (248, 255, 246), "edge": (10, 80, 35),
     "black": (15, 60, 30), "red": (200, 30, 40), "frame": True,
     "motif": "shamrock", "motif_color": (20, 140, 60), "trim": (250, 215, 70)},
]
CUSTOM_STYLE = dict(CARD_STYLES[0], name="My Images", custom=True)
STYLES = list(CARD_STYLES)        # init_graphics adds "My Images" if you have a cards folder


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def heart_points(tip_x, tip_y, size, angle=0.0):
    """Outline of a heart whose bottom tip is at (tip_x, tip_y), `size` tall.
    angle (degrees) rotates it around the tip."""
    pts = []
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    scale = size / 29.0
    for k in range(48):
        t = 2 * math.pi * k / 48
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) - 17
        x, y = x * scale, y * scale
        pts.append((tip_x + x * ca - y * sa, tip_y + x * sa + y * ca))
    return pts


def draw_motif(surf, kind, cx, cy, s, color):
    """Small themed icon centered at (cx, cy), about 2*s across."""
    if kind == "spade":
        draw_suit(surf, SPADES, cx, cy, s * 2, color)
    elif kind == "heart":
        pygame.draw.polygon(surf, color, heart_points(cx, cy + s, s * 2))
    elif kind == "teddy":  # teddy bear head (not a suit, so safe on card faces)
        tan, dark = (242, 208, 165), (55, 28, 22)
        for sx in (-1, 1):  # ears
            ear = P(cx + sx * 0.72 * s, cy - 0.68 * s)
            pygame.draw.circle(surf, color, ear, max(2, int(0.4 * s)))
            pygame.draw.circle(surf, mix(color, (255, 190, 190), 0.6), ear, max(1, int(0.2 * s)))
        pygame.draw.circle(surf, color, P(cx, cy + 0.1 * s), int(0.9 * s))  # head
        muzzle = pygame.Rect(0, 0, int(1.0 * s), int(0.75 * s))
        muzzle.center = P(cx, cy + 0.42 * s)
        pygame.draw.ellipse(surf, tan, muzzle)
        nose = pygame.Rect(0, 0, max(2, int(0.36 * s)), max(2, int(0.25 * s)))
        nose.center = P(cx, cy + 0.27 * s)
        pygame.draw.ellipse(surf, dark, nose)
        for sx in (-1, 1):  # eyes
            pygame.draw.circle(surf, dark, P(cx + sx * 0.36 * s, cy - 0.12 * s), max(1, int(0.13 * s)))
        if s >= 11:
            pygame.draw.line(surf, dark, P(cx, cy + 0.4 * s), P(cx, cy + 0.55 * s), 1)
    elif kind == "star":
        pts = []
        for k in range(10):
            r = s if k % 2 == 0 else s * 0.42
            ang = -math.pi / 2 + k * math.pi / 5
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        pygame.draw.polygon(surf, color, pts)
    elif kind == "snowflake":
        w = 2 if s >= 9 else 1
        for k in range(6):
            ang = math.radians(k * 60)
            dx, dy = math.cos(ang), math.sin(ang)
            pygame.draw.line(surf, color, (cx, cy), (cx + s * dx, cy + s * dy), w)
            bx, by = cx + 0.62 * s * dx, cy + 0.62 * s * dy
            for side in (-1, 1):
                a2 = ang + side * math.radians(50)
                pygame.draw.line(surf, color, (bx, by),
                                 (bx + 0.34 * s * math.cos(a2), by + 0.34 * s * math.sin(a2)), w)
    elif kind == "pumpkin":
        dark = (45, 25, 0)
        for ox, ww in ((-0.5, 1.0), (0.5, 1.0), (0.0, 1.15)):
            r = pygame.Rect(0, 0, int(s * ww * 1.15), int(s * 1.5))
            r.center = (int(cx + ox * s), int(cy + 0.15 * s))
            pygame.draw.ellipse(surf, color, r)
            pygame.draw.ellipse(surf, mix(color, dark, 0.45), r, 1)
        pygame.draw.rect(surf, (40, 120, 40), (int(cx - 0.12 * s), int(cy - 0.8 * s),
                                               max(2, int(0.28 * s)), max(2, int(0.4 * s))))
        if s >= 11:  # carved face
            for ex in (-0.42, 0.42):
                pygame.draw.polygon(surf, dark, [(cx + ex * s, cy - 0.2 * s),
                                                 (cx + (ex - 0.2) * s, cy + 0.15 * s),
                                                 (cx + (ex + 0.2) * s, cy + 0.15 * s)])
            pygame.draw.polygon(surf, dark, [(cx - 0.5 * s, cy + 0.4 * s), (cx + 0.5 * s, cy + 0.4 * s),
                                             (cx + 0.2 * s, cy + 0.7 * s), (cx - 0.2 * s, cy + 0.7 * s)])
    elif kind == "shamrock":
        for ang in (0, 120, 240):
            pygame.draw.polygon(surf, color, heart_points(cx, cy + 0.1 * s, s * 1.15, ang))
        pygame.draw.line(surf, mix(color, (0, 0, 0), 0.35), (cx, cy + 0.1 * s),
                         (cx + 0.18 * s, cy + 1.25 * s), 2)


def make_back(style):
    base, accent = style["back"], style["accent"]
    surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
    rect = surf.get_rect()
    pygame.draw.rect(surf, base, rect, border_radius=9)
    inner = rect.inflate(-14, -14)
    surf.set_clip(inner)
    pygame.draw.rect(surf, style.get("field") or mix(base, (255, 255, 255), 0.12), inner)
    pattern = style["pattern"]
    if pattern == "diamonds":
        for i in range(-CARD_H, CARD_W + CARD_H, 14):
            pygame.draw.line(surf, accent, (i, 0), (i + CARD_H, CARD_H), 1)
            pygame.draw.line(surf, accent, (i + CARD_H, 0), (i, CARD_H), 1)
    elif pattern == "stripes":
        for i in range(-CARD_H, CARD_W + CARD_H, 17):
            pygame.draw.line(surf, accent, (i, 0), (i + CARD_H, CARD_H), 6)
    elif pattern == "vstripes":
        for x in range(inner.left, inner.right, 18):
            pygame.draw.rect(surf, accent, (x, inner.top, 9, inner.height))
    elif pattern == "dots":
        for row, y in enumerate(range(inner.top + 6, inner.bottom, 14)):
            for x in range(inner.left + (7 if row % 2 else 0), inner.right, 14):
                pygame.draw.circle(surf, accent, (x, y), 3)
    elif pattern == "checks":
        for row, y in enumerate(range(inner.top, inner.bottom, 12)):
            for col, x in enumerate(range(inner.left, inner.right, 12)):
                if (row + col) % 2 == 0:
                    pygame.draw.rect(surf, accent, (x, y, 12, 12))
    surf.set_clip(None)
    pygame.draw.rect(surf, style.get("trim", (255, 255, 255)), inner, width=2, border_radius=4)
    pygame.draw.rect(surf, mix(base, (0, 0, 0), 0.6), rect, width=2, border_radius=9)
    if style.get("motif"):
        c = (CARD_W // 2, CARD_H // 2)
        pygame.draw.circle(surf, style.get("medal", style["face"]), c, 23)
        pygame.draw.circle(surf, style.get("trim", style["edge"]), c, 23, 3)
        draw_motif(surf, style["motif"], c[0], c[1], 13, style["motif_color"])
    return surf


def make_face(card, style):
    suit, value = card
    surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
    rect = surf.get_rect()
    pygame.draw.rect(surf, style["face"], rect, border_radius=9)
    if style.get("frame"):
        pygame.draw.rect(surf, mix(style["face"], style["back"], 0.4), rect.inflate(-8, -8),
                         width=1, border_radius=6)
    pygame.draw.rect(surf, style["edge"], rect, width=2, border_radius=9)
    color = style["red"] if suit in (HEARTS, DIAMONDS) else style["black"]

    corner = pygame.Surface((30, 46), pygame.SRCALPHA)
    label = FONT_CARD.render(rank_label(value), True, color)
    corner.blit(label, ((30 - label.get_width()) // 2, 0))
    draw_suit(corner, suit, 15, 34, 15, color)
    surf.blit(corner, (4, 4))
    surf.blit(pygame.transform.rotate(corner, 180), (CARD_W - 34, CARD_H - 50))

    draw_suit(surf, suit, CARD_W // 2, CARD_H // 2, 48, color)
    # Holiday icons in the two free corners. Suit-shaped icons (spade, heart) stay off the
    # faces so they can't be mistaken for the card's suit.
    if style.get("motif") and style.get("face_motif", True):
        draw_motif(surf, style["motif"], CARD_W - 17, 17, 9, style["motif_color"])
        draw_motif(surf, style["motif"], 17, CARD_H - 17, 9, style["motif_color"])
    return surf


def grayed(surf):
    """A dull gray copy of a card, for cards you can't play right now."""
    try:
        g = pygame.transform.grayscale(surf)
    except AttributeError:  # very old pygame: no grayscale, just darken it
        g = surf.copy()
    g.fill((185, 185, 185, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return g


def load_card_image(name):
    """Load cards/<name>.jpg (or .jpeg / .png), scaled to card size. None if missing."""
    for ext in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"):
        path = os.path.join(CARD_DIR, name + ext)
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
            except pygame.error:
                return None
            img = pygame.transform.smoothscale(img, (CARD_W, CARD_H))
            pygame.draw.rect(img, (40, 40, 40), img.get_rect(), width=1)
            return img
    return None


def has_custom_images():
    if not os.path.isdir(CARD_DIR):
        return False
    return any(f.lower().endswith((".jpg", ".jpeg", ".png")) for f in os.listdir(CARD_DIR))


ASSET_CACHE = {}
PREVIEW_CACHE = {}


def assets_for(style):
    """All 52 faces (plus gray versions) and the back for a style, built once."""
    name = style["name"]
    if name not in ASSET_CACHE:
        faces = {}
        for card in make_deck():
            img = load_card_image(f"{rank_label(card[1])}{card[0]}") if style.get("custom") else None
            faces[card] = img or make_face(card, style)
        back = (load_card_image("back") if style.get("custom") else None) or make_back(style)
        ASSET_CACHE[name] = {"faces": faces,
                             "gray": {c: grayed(s) for c, s in faces.items()},
                             "back": back,
                             "back_side": pygame.transform.rotate(back, 90)}
    return ASSET_CACHE[name]


def preview_for(style):
    """Small back + face pictures for the options screen."""
    name = style["name"]
    if name not in PREVIEW_CACHE:
        a = assets_for(style)
        size = (60, 86)
        PREVIEW_CACHE[name] = (pygame.transform.smoothscale(a["back"], size),
                               pygame.transform.smoothscale(a["faces"][(SPADES, 14)], size))
    return PREVIEW_CACHE[name]


def style_by_name(name):
    for s in STYLES:
        if s["name"] == name:
            return s
    return STYLES[0]


def apply_style(name):
    global FACES, GRAY_FACES, BACK, BACK_SIDE
    a = assets_for(style_by_name(name))
    FACES, GRAY_FACES, BACK, BACK_SIDE = a["faces"], a["gray"], a["back"], a["back_side"]


# ----------------------------- Graphics -----------------------------
screen = None
FONT_XS = FONT_S = FONT_M = FONT_L = FONT_CARD = None
FACES = {}
GRAY_FACES = {}
BACK = BACK_SIDE = None


def P(x, y):
    return int(x), int(y)


def draw_suit(surf, suit, cx, cy, size, color):
    """Draw a suit symbol with shapes (no font needed). size is roughly its height."""
    s = size
    if suit == HEARTS:
        r = int(0.27 * s)
        pygame.draw.circle(surf, color, P(cx - 0.25 * s, cy - 0.17 * s), r)
        pygame.draw.circle(surf, color, P(cx + 0.25 * s, cy - 0.17 * s), r)
        pygame.draw.polygon(surf, color, [P(cx - 0.50 * s, cy - 0.07 * s),
                                          P(cx + 0.50 * s, cy - 0.07 * s),
                                          P(cx, cy + 0.50 * s)])
    elif suit == DIAMONDS:
        pygame.draw.polygon(surf, color, [P(cx, cy - 0.50 * s), P(cx + 0.35 * s, cy),
                                          P(cx, cy + 0.50 * s), P(cx - 0.35 * s, cy)])
    elif suit == SPADES:
        r = int(0.27 * s)
        pygame.draw.polygon(surf, color, [P(cx, cy - 0.50 * s),
                                          P(cx - 0.50 * s, cy + 0.07 * s),
                                          P(cx + 0.50 * s, cy + 0.07 * s)])
        pygame.draw.circle(surf, color, P(cx - 0.25 * s, cy + 0.17 * s), r)
        pygame.draw.circle(surf, color, P(cx + 0.25 * s, cy + 0.17 * s), r)
        pygame.draw.polygon(surf, color, [P(cx, cy + 0.10 * s),
                                          P(cx - 0.18 * s, cy + 0.50 * s),
                                          P(cx + 0.18 * s, cy + 0.50 * s)])
    else:  # clubs
        r = max(1, int(0.24 * s))
        pygame.draw.circle(surf, color, P(cx, cy - 0.24 * s), r)
        pygame.draw.circle(surf, color, P(cx - 0.26 * s, cy + 0.08 * s), r)
        pygame.draw.circle(surf, color, P(cx + 0.26 * s, cy + 0.08 * s), r)
        pygame.draw.circle(surf, color, P(cx, cy - 0.02 * s), max(1, int(0.20 * s)))
        pygame.draw.polygon(surf, color, [P(cx, cy + 0.05 * s),
                                          P(cx - 0.18 * s, cy + 0.50 * s),
                                          P(cx + 0.18 * s, cy + 0.50 * s)])


def init_graphics():
    global screen, FONT_XS, FONT_S, FONT_M, FONT_L, FONT_CARD, STYLES
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Spades")
    FONT_XS = pygame.font.SysFont("arial", 15)
    FONT_S = pygame.font.SysFont("arial", 18)
    FONT_M = pygame.font.SysFont("arial", 24, bold=True)
    FONT_L = pygame.font.SysFont("arial", 44, bold=True)
    FONT_CARD = pygame.font.SysFont("arial", 22, bold=True)
    STYLES = list(CARD_STYLES) + ([CUSTOM_STYLE] if has_custom_images() else [])
    apply_style(DEFAULT_SETTINGS["style"])


def draw_text(text, font, color, pos, align="left"):
    img = font.render(text, True, color)
    r = img.get_rect()
    if align == "center":
        r.midtop = pos
    elif align == "right":
        r.topright = pos
    else:
        r.topleft = pos
    screen.blit(img, r)
    return r


def draw_panel(rect, alpha=150, radius=12):
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, (0, 0, 0, alpha), panel.get_rect(), border_radius=radius)
    screen.blit(panel, rect.topleft)


def draw_button(rect, label, mouse, primary=False, selected=False, font=None):
    font = font or FONT_M
    hover = rect.collidepoint(mouse)
    draw_panel(rect.move(0, 4), 110, 12)
    if selected:
        fill, ink = (255, 215, 0), (45, 28, 0)
    elif primary:
        fill, ink = ((255, 236, 150) if hover else (255, 205, 60)), (45, 28, 0)
    else:
        fill, ink = ((255, 255, 255) if hover else (236, 238, 232)), (25, 25, 25)
    pygame.draw.rect(screen, fill, rect, border_radius=12)
    pygame.draw.rect(screen, (255, 255, 255) if selected else mix(fill, (0, 0, 0), 0.35),
                     rect, width=2, border_radius=12)
    img = font.render(label, True, ink)
    screen.blit(img, img.get_rect(center=rect.center))


_TEXT_CACHE = {}


def outlined_text(text, size, color, outline, thickness=4):
    """Big bold text with a dark outline. Cached, since it is redrawn every frame."""
    key = (text, size, color, outline, thickness)
    if key not in _TEXT_CACHE:
        font = pygame.font.SysFont("arial", size, bold=True)
        base, edge = font.render(text, True, color), font.render(text, True, outline)
        w, h = base.get_size()
        surf = pygame.Surface((w + 2 * thickness, h + 2 * thickness), pygame.SRCALPHA)
        for dx in range(-thickness, thickness + 1):
            for dy in range(-thickness, thickness + 1):
                if dx * dx + dy * dy <= thickness * thickness:
                    surf.blit(edge, (dx + thickness, dy + thickness))
        surf.blit(base, (thickness, thickness))
        _TEXT_CACHE[key] = surf
    return _TEXT_CACHE[key]


_VIGNETTE = None


def draw_felt():
    """Green table with darker edges."""
    global _VIGNETTE
    screen.fill(TABLE_GREEN)
    if _VIGNETTE is None:
        v = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for i in range(60):
            a = int(110 * (1 - i / 60) ** 2)
            pygame.draw.rect(v, (0, 0, 0, a), pygame.Rect(0, 0, WIDTH, HEIGHT).inflate(-2 * i * 3, -2 * i * 3),
                             width=6)
        _VIGNETTE = v
    screen.blit(_VIGNETTE, (0, 0))


def seat_label(game, seat):
    text = f"{SEAT_NAMES[seat]}  |  bid {bid_text(game.bids[seat])}  |  won {game.tricks_won[seat]}"
    color = (255, 215, 0) if game.actor() == seat else (255, 255, 255)
    return text, color


def draw_seat_tag(game, seat, x, y, align, now):
    """Name and bid for one seat. While bidding is going on (until the round starts)
    this is a big tag: the player whose turn it is to bid glows, and every bid that
    has been made is highlighted."""
    if game.phase not in ("bidding", "bids_review"):
        text, color = seat_label(game, seat)
        draw_text(text, FONT_S, color, (x, y), align)
        return

    is_actor = game.actor() == seat
    bid = game.bids[seat]
    name_img = FONT_M.render(SEAT_NAMES[seat], True, (40, 25, 0) if is_actor else (255, 255, 255))
    bid_str = "..." if bid is None else bid_text(bid)
    bid_img = FONT_M.render("bid " + bid_str, True, (20, 20, 20) if bid is not None else (200, 200, 200))
    pad, gap, h = 12, 8, 34
    w_name, w_bid = name_img.get_width() + 2 * pad, bid_img.get_width() + 2 * pad
    total = w_name + gap + w_bid
    left = x - total // 2 if align == "center" else (x - total if align == "right" else x)

    name_rect = pygame.Rect(left, y, w_name, h)
    if is_actor:  # glowing gold pill: this player is bidding right now
        pulse = (math.sin(now / 140.0) + 1) / 2
        pygame.draw.rect(screen, (255, 235, 140), name_rect.inflate(12, 12), width=3, border_radius=15)
        pygame.draw.rect(screen, (255, int(195 + 45 * pulse), int(30 + 70 * pulse)), name_rect, border_radius=10)
    else:
        draw_panel(name_rect, 170, 10)
    screen.blit(name_img, name_img.get_rect(center=name_rect.center))

    bid_rect = pygame.Rect(left + w_name + gap, y, w_bid, h)
    if bid is None:  # hasn't bid yet
        draw_panel(bid_rect, 110, 10)
        pygame.draw.rect(screen, (190, 190, 190), bid_rect, width=1, border_radius=10)
    else:            # bid made: bright badge, stays until the round starts
        pygame.draw.rect(screen, (250, 250, 240), bid_rect, border_radius=10)
        pygame.draw.rect(screen, (255, 200, 0), bid_rect, width=3, border_radius=10)
    screen.blit(bid_img, bid_img.get_rect(center=bid_rect.center))


def draw(game, now, mouse):
    """Draw the card table for a match (and the match-over screen when it ends)."""
    screen.fill(TABLE_GREEN)

    # Scoreboard (top left) and hand info (top right)
    box = pygame.Rect(20, 20, 270, 90)
    draw_panel(box)
    draw_text(f"Score (first to {game.target})", FONT_S, (200, 230, 200), (32, 26))
    draw_text(f"Your team:  {game.scores[0]}   (bags {game.bags[0]})", FONT_S, (255, 255, 255), (32, 52))
    draw_text(f"Opponents:  {game.scores[1]}   (bags {game.bags[1]})", FONT_S, (255, 255, 255), (32, 76))

    info = pygame.Rect(WIDTH - 290, 20, 270, 90)
    draw_panel(info)
    draw_text(f"Trick {game.trick_number()} of 13", FONT_S, (255, 255, 255), (WIDTH - 278, 28))
    draw_text(f"Playing to {game.target}", FONT_S, (255, 255, 255), (WIDTH - 278, 52))
    first = game.bid_order[0]
    draw_text("You bid first this hand" if first == 0 else f"{SEAT_NAMES[first]} bid first this hand",
              FONT_S, (200, 230, 200), (WIDTH - 278, 76))

    # North (top), West (left), East (right): face-down cards
    n = len(game.hands[2])
    if n:
        total = 30 * (n - 1) + CARD_W
        x0 = (WIDTH - total) // 2
        for i in range(n):
            screen.blit(BACK, (x0 + i * 30, 20))
    draw_seat_tag(game, 2, WIDTH // 2, 20 + CARD_H + 8, "center", now)

    side_total = 24 * 12 + CARD_W
    y0 = (HEIGHT - side_total) // 2 - 20
    for i in range(len(game.hands[1])):
        screen.blit(BACK_SIDE, (30, y0 + i * 24))
    draw_seat_tag(game, 1, 30, y0 - 40, "left", now)
    for i in range(len(game.hands[3])):
        screen.blit(BACK_SIDE, (WIDTH - 30 - CARD_H, y0 + i * 24))
    draw_seat_tag(game, 3, WIDTH - 30, y0 - 40, "right", now)

    # Cards on the table
    positions = trick_positions()
    for seat, card in game.trick:
        x, y = positions[seat]
        screen.blit(FACES[card], (x, y))
        if game.phase == "trick_done" and seat == game.trick_winner:
            pygame.draw.rect(screen, (255, 215, 0),
                             pygame.Rect(x, y, CARD_W, CARD_H).inflate(10, 10),
                             width=4, border_radius=12)

    # Status line (or a short warning if you tried an illegal card)
    if now < game.flash_until:
        draw_text(game.flash_text, FONT_M, (255, 190, 90), (WIDTH // 2, 545), "center")
    else:
        status = game.status_text()
        if status:
            draw_text(status, FONT_M, (255, 255, 255), (WIDTH // 2, 545), "center")

    # Your hand. Cards you can't play right now (including spades until they are
    # allowed) are grayed out.
    hand = game.hands[0]
    rects = hand_rects(len(hand))
    legal = game.hint_legal()
    hover = None
    if game.phase == "playing" and game.turn == 0:
        for i in range(len(rects) - 1, -1, -1):
            if rects[i].collidepoint(mouse):
                hover = i
                break

    draw_seat_tag(game, 0, WIDTH // 2, HEIGHT - CARD_H - 30 - 50, "center", now)

    order = [i for i in range(len(hand)) if i != hover]
    if hover is not None:
        order.append(hover)  # draw the hovered card last so it sits on top
    for i in order:
        card, r = hand[i], rects[i]
        playable = legal is None or card in legal
        pos = (r.x, r.y - 18 if (i == hover and playable) else r.y)
        screen.blit(FACES[card] if playable else GRAY_FACES[card], pos)

    # Bid buttons
    if game.human_must_bid():
        draw_panel(pygame.Rect(250, 250, 600, 200), 200)
        draw_text("Your bid", FONT_M, (255, 255, 255), (WIDTH // 2, 262), "center")
        draw_text("Bid for your own hand: how many tricks will YOU take?  Nil = none.",
                  FONT_S, (210, 230, 210), (WIDTH // 2, 298), "center")
        for value, rect in enumerate(bid_button_rects()):
            hovering = rect.collidepoint(mouse)
            pygame.draw.rect(screen, (255, 235, 150) if hovering else (240, 240, 235),
                             rect, border_radius=8)
            label = "Nil" if value == 0 else str(value)
            img = FONT_M.render(label, True, (20, 20, 20))
            screen.blit(img, img.get_rect(center=rect.center))

    # All four bids are in: show them together until you click to start the round
    if game.phase == "bids_review":
        panel = pygame.Rect(300, 245, 500, 225)
        draw_panel(panel, 215)
        draw_text("Bids are in", FONT_M, (255, 215, 0), (WIDTH // 2, panel.y + 14), "center")
        y = panel.y + 58
        table_total = 0
        for team, seats in ((0, (0, 2)), (1, (1, 3))):
            parts = " + ".join(f"{SEAT_NAMES[s]} {bid_text(game.bids[s])}" for s in seats)
            contract = sum(game.bids[s] for s in seats if game.bids[s] > 0)
            table_total += contract
            draw_text(f"{TEAM_NAMES[team]}:  {parts}  =  {contract}", FONT_S,
                      (255, 255, 255), (WIDTH // 2, y), "center")
            y += 30
        draw_text(f"Table total: {table_total} of 13 tricks", FONT_S,
                  (200, 230, 200), (WIDTH // 2, y + 4), "center")
        y += 32
        if table_total > 13:
            draw_text("The table bid over 13, so someone will be set", FONT_S,
                      (255, 190, 90), (WIDTH // 2, y + 4), "center")
        draw_text("Click anywhere to start the round", FONT_M, (255, 255, 255),
                  (WIDTH // 2, panel.bottom - 44), "center")

    # Menu / History buttons
    match_over = game.phase == "hand_over" and game.finished
    if not match_over:
        draw_button(GAME_MENU_RECT, "Menu", mouse, font=FONT_S)
        draw_button(GAME_HISTORY_RECT, "History", mouse, font=FONT_S)

    # Results after each hand, or the big celebration when the match ends
    if match_over:
        draw_match_over(game, now, mouse)
    elif game.phase == "hand_over":
        dim_all = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim_all.fill((0, 0, 0, 120))
        screen.blit(dim_all, (0, 0))
        panel = pygame.Rect(150, 200, 800, 320)
        draw_panel(panel, 225)
        draw_text("Hand results", FONT_L, (255, 215, 0), (WIDTH // 2, panel.y + 20), "center")
        y = panel.y + 100
        for line in game.result_lines:
            draw_text(line, FONT_S, (255, 255, 255), (WIDTH // 2, y), "center")
            y += 32
        draw_text(f"Score:   Your team {game.scores[0]}   |   Opponents {game.scores[1]}",
                  FONT_M, (255, 255, 255), (WIDTH // 2, y + 14), "center")
        draw_text("Click to continue", FONT_S, (200, 230, 200), (WIDTH // 2, panel.bottom - 44), "center")


# ----------------------------- Match over ---------------------------
CONFETTI_COLORS = [(255, 80, 100), (255, 200, 40), (80, 220, 140), (80, 170, 255),
                   (200, 110, 255), (255, 255, 255), (255, 140, 50)]
PASTELS = [(255, 170, 200), (255, 220, 120), (150, 230, 255), (200, 170, 255), (170, 255, 200)]
_BG_CACHE = {}
_PARTICLES = {}
_RAYS = None


def gradient_surface(top, bottom):
    key = (top, bottom)
    if key not in _BG_CACHE:
        surf = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            pygame.draw.line(surf, mix(top, bottom, y / (HEIGHT - 1)), (0, y), (WIDTH, y))
        _BG_CACHE[key] = surf
    return _BG_CACHE[key]


def particles(win):
    if win not in _PARTICLES:
        rng = random.Random(7 if win else 11)
        _PARTICLES[win] = [{
            "x": rng.uniform(0, WIDTH), "phase": rng.uniform(0, 2000),
            "speed": rng.uniform(80, 240), "size": rng.uniform(7, 15),
            "spin": rng.uniform(-7, 7), "sway": rng.uniform(10, 45),
            "color": rng.choice(CONFETTI_COLORS if win else PASTELS),
            "shape": rng.choice(["rect", "rect", "circle"]),
            "suit": rng.choice(SUIT_ORDER),
        } for _ in range(150 if win else 38)]
    return _PARTICLES[win]


def draw_particles(win, t):
    for p in particles(win):
        x = p["x"] + math.sin(t * 1.6 + p["phase"]) * p["sway"]
        if win:   # confetti rains down
            y = (p["phase"] + t * p["speed"]) % (HEIGHT + 60) - 30
            if p["shape"] == "circle":
                pygame.draw.circle(screen, p["color"], P(x, y), int(p["size"] / 2.2))
            else:
                a = t * p["spin"] + p["phase"]
                w, h = p["size"], p["size"] * 0.55
                pts = []
                for cx, cy in ((-w, -h), (w, -h), (w, h), (-w, h)):
                    cx, cy = cx / 2, cy / 2
                    pts.append((x + cx * math.cos(a) - cy * math.sin(a),
                                y + cx * math.sin(a) + cy * math.cos(a)))
                pygame.draw.polygon(screen, p["color"], pts)
        else:     # suits drift gently upward
            y = HEIGHT + 50 - ((p["phase"] + t * p["speed"] * 0.45) % (HEIGHT + 100))
            draw_suit(screen, p["suit"], x, y, p["size"] * 3.2, p["color"])


def draw_rays(cx, cy, t, rgba, count=18, speed=0.12):
    global _RAYS
    if _RAYS is None:
        _RAYS = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    _RAYS.fill((0, 0, 0, 0))
    step = 2 * math.pi / count
    for i in range(count):
        a0 = t * speed + i * step
        a1 = a0 + step * 0.5
        pygame.draw.polygon(_RAYS, rgba, [(cx, cy),
                                          (cx + 1500 * math.cos(a0), cy + 1500 * math.sin(a0)),
                                          (cx + 1500 * math.cos(a1), cy + 1500 * math.sin(a1))])
    screen.blit(_RAYS, (0, 0))


def draw_trophy(cx, cy, s):
    gold, dark, light = (255, 200, 40), (200, 140, 10), (255, 238, 150)
    pygame.draw.rect(screen, dark, pygame.Rect(cx - 0.45 * s, cy + 0.78 * s, 0.9 * s, 0.17 * s), border_radius=6)
    pygame.draw.rect(screen, gold, pygame.Rect(cx - 0.32 * s, cy + 0.6 * s, 0.64 * s, 0.2 * s), border_radius=4)
    pygame.draw.rect(screen, dark, pygame.Rect(cx - 0.09 * s, cy + 0.28 * s, 0.18 * s, 0.36 * s))
    lw = max(3, int(0.09 * s))
    pygame.draw.arc(screen, gold, pygame.Rect(cx - 0.9 * s, cy - 0.68 * s, 0.7 * s, 0.7 * s),
                    math.pi / 2, 3 * math.pi / 2, lw)
    pygame.draw.arc(screen, gold, pygame.Rect(cx + 0.2 * s, cy - 0.68 * s, 0.7 * s, 0.7 * s),
                    -math.pi / 2, math.pi / 2, lw)
    pygame.draw.polygon(screen, gold, [P(cx - 0.55 * s, cy - 0.78 * s), P(cx + 0.55 * s, cy - 0.78 * s),
                                       P(cx + 0.42 * s, cy - 0.02 * s), P(cx + 0.2 * s, cy + 0.32 * s),
                                       P(cx - 0.2 * s, cy + 0.32 * s), P(cx - 0.42 * s, cy - 0.02 * s)])
    pygame.draw.polygon(screen, light, [P(cx - 0.42 * s, cy - 0.7 * s), P(cx - 0.26 * s, cy - 0.7 * s),
                                        P(cx - 0.18 * s, cy - 0.05 * s), P(cx - 0.3 * s, cy - 0.05 * s)])
    pygame.draw.ellipse(screen, light, pygame.Rect(cx - 0.55 * s, cy - 0.87 * s, 1.1 * s, 0.18 * s))
    pygame.draw.ellipse(screen, dark, pygame.Rect(cx - 0.55 * s, cy - 0.87 * s, 1.1 * s, 0.18 * s), 2)
    draw_motif(screen, "star", cx, cy - 0.38 * s, 0.2 * s, (255, 250, 220))


def draw_sparkles(t, centers):
    for i, (x, y, r) in enumerate(centers):
        k = (math.sin(t * 3 + i * 1.7) + 1) / 2
        rr = r * (0.35 + 0.65 * k)
        pts = [(x, y - rr), (x + rr * 0.22, y - rr * 0.22), (x + rr, y), (x + rr * 0.22, y + rr * 0.22),
               (x, y + rr), (x - rr * 0.22, y + rr * 0.22), (x - rr, y), (x - rr * 0.22, y - rr * 0.22)]
        pygame.draw.polygon(screen, (255, 255, 235), pts)


def draw_fan(surfs, cx, cy, spread=15, radius=95):
    n = len(surfs)
    for i, s in enumerate(surfs):
        ang = (i - (n - 1) / 2) * spread
        rot = pygame.transform.rotozoom(s, -ang, 1.3)
        a = math.radians(ang)
        screen.blit(rot, rot.get_rect(center=(cx + radius * math.sin(a), cy - radius * math.cos(a))))


def pop_scale(t):
    """Ease-out-back: grows past full size, then settles."""
    x = max(0.0, min(1.0, t / 0.6))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def draw_match_over(game, now, mouse):
    win = game.winner() == 0
    t = max(0.0, (now - game.stamp) / 1000.0)
    top, bottom = ((110, 25, 170), (255, 125, 45)) if win else ((25, 35, 120), (215, 70, 150))
    screen.blit(gradient_surface(top, bottom), (0, 0))
    draw_rays(WIDTH // 2, 270, t, (255, 240, 170, 40) if win else (170, 190, 255, 34))
    draw_particles(win, t)

    if win:
        bob = math.sin(t * 2.2) * 7
        draw_trophy(WIDTH // 2, 235 + bob, 120)
        draw_sparkles(t, [(WIDTH // 2 - 210, 150, 22), (WIDTH // 2 + 215, 190, 26),
                          (WIDTH // 2 - 150, 330, 16), (WIDTH // 2 + 160, 120, 18),
                          (WIDTH // 2 + 90, 340, 14)])
        title = outlined_text("YOU WIN!", 118, (255, 228, 70), (70, 10, 100), 6)
        sub = "Congratulations, champions!"
    else:
        bob = math.sin(t * 2.0) * 5
        faces = [FACES[(SPADES, 14)], FACES[(HEARTS, 13)], FACES[(CLUBS, 12)], FACES[(DIAMONDS, 11)]]
        draw_fan(faces, WIDTH // 2, 290 + bob, spread=17, radius=125)
        title = outlined_text("Better Luck Next Time", 70, (255, 255, 255), (50, 15, 110), 5)
        sub = "Good game! Shuffle up and go again."

    scale = pop_scale(t)
    wobble = math.sin(t * 2.4) * 1.5 if t > 0.6 else 0
    big = pygame.transform.rotozoom(title, wobble, max(0.05, scale))
    screen.blit(big, big.get_rect(center=(WIDTH // 2, 435)))

    sub_img = FONT_M.render(sub, True, (255, 255, 255))
    screen.blit(sub_img, sub_img.get_rect(center=(WIDTH // 2, 515)))

    panel = pygame.Rect(0, 0, 560, 70)
    panel.center = (WIDTH // 2, 580)
    draw_panel(panel, 165, 18)
    ours, theirs = game.scores
    line = f"Final score:   Your team {ours}   -   Opponents {theirs}"
    img = FONT_M.render(line, True, (255, 255, 255))
    screen.blit(img, img.get_rect(center=panel.center))

    labels = ["Play Again" if win else "Rematch", "Main Menu", "View History"]
    for i, (rect, label) in enumerate(zip(match_over_rects(), labels)):
        draw_button(rect, label, mouse, primary=(i == 0))


# ----------------------------- Menu and options ---------------------
def draw_menu(app, now, mouse):
    draw_felt()
    bob = math.sin(now / 600.0) * 4
    title = outlined_text("SPADES", 128, (255, 255, 255), (8, 45, 22), 7)
    screen.blit(title, title.get_rect(center=(WIDTH // 2, 118 + bob)))
    draw_suit(screen, SPADES, 205, 125 + bob, 115, (255, 215, 0))
    draw_suit(screen, SPADES, WIDTH - 205, 125 + bob, 115, (255, 215, 0))
    sub = FONT_M.render("You and North  vs.  West and East", True, (210, 240, 215))
    screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 222)))

    draw_fan([FACES[(SPADES, 14)], FACES[(SPADES, 13)], FACES[(SPADES, 12)]], 170, 560, 20, 100)
    draw_fan([FACES[(HEARTS, 14)], FACES[(DIAMONDS, 14)], FACES[(CLUBS, 14)]], WIDTH - 170, 560, 20, 100)

    items = menu_items(app.resumable())
    for (key, label), rect in zip(items, menu_rects(items)):
        draw_button(rect, label, mouse, primary=(key in ("new", "resume")))

    s = app.settings
    line = (f"Partner: {s['partner']}     Opponents: {s['opponents']}     "
            f"Playing to {s['target']}     Cards: {s['style']}")
    img = FONT_S.render(line, True, (205, 235, 210))
    screen.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 48)))


def draw_options(app, now, mouse):
    draw_felt()
    draw_button(BACK_RECT, "< Back", mouse, font=FONT_S)
    title = outlined_text("Options", 54, (255, 255, 255), (8, 45, 22), 4)
    screen.blit(title, title.get_rect(center=(WIDTH // 2, 48)))
    s = app.settings

    rows = [("Your partner (North)", OPT_PARTNER_Y, LEVELS, s["partner"], LEVEL_INFO[s["partner"]]),
            ("Opponents (West & East)", OPT_OPP_Y, LEVELS, s["opponents"], LEVEL_INFO[s["opponents"]]),
            ("Play to", OPT_TARGET_Y, TARGETS, s["target"],
             "First team to this many points wins the match")]
    for label, y, values, current, note in rows:
        draw_text(label, FONT_M, (255, 255, 255), (60, y + 10))
        for value, rect in zip(values, seg_rects(OPT_SEG_X, y, len(values))):
            draw_button(rect, str(value), mouse, selected=(value == current))
        draw_text(note, FONT_S, (200, 230, 205), (OPT_SEG_X, y + 52))

    draw_text("Card style", FONT_M, (255, 255, 255), (60, 362))
    for style, rect in zip(STYLES, style_cell_rects(len(STYLES))):
        chosen = style["name"] == s["style"]
        hover = rect.collidepoint(mouse)
        draw_panel(rect, 150 if hover else 105, 14)
        if chosen:
            pygame.draw.rect(screen, (255, 215, 0), rect, width=4, border_radius=14)
        elif hover:
            pygame.draw.rect(screen, (255, 255, 255), rect, width=2, border_radius=14)
        back, face = preview_for(style)
        screen.blit(back, (rect.x + 30, rect.y + 12))
        screen.blit(face, (rect.x + 100, rect.y + 12))
        name = FONT_S.render(style["name"], True, (255, 235, 150) if chosen else (255, 255, 255))
        screen.blit(name, name.get_rect(center=(rect.centerx, rect.y + 126)))
        if chosen:
            tag = FONT_XS.render("Selected", True, (255, 215, 0))
            screen.blit(tag, tag.get_rect(center=(rect.centerx, rect.y + 148)))

    note = "Difficulty and points apply to your next new game. Card style changes right away."
    img = FONT_XS.render(note, True, (205, 235, 210))
    screen.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 16)))


# ----------------------------- Match history ------------------------
HIST_COLS = [("rd", 50, 44), ("s0", 94, 84), ("s1", 178, 84), ("s2", 262, 84), ("s3", 346, 84),
             ("p0", 430, 82), ("p1", 512, 82), ("t0", 594, 92), ("t1", 686, 92),
             ("g0", 778, 62), ("g1", 840, 62), ("b0", 902, 62), ("b1", 964, 62)]
HIST_COL = {k: (x, w) for k, x, w in HIST_COLS}
HIST_GROUPS = [("Bid / Took", 94, 430), ("Round points", 430, 594), ("Total score", 594, 778),
               ("Bags gained", 778, 902), ("Total bags", 902, 1026)]
HIST_SUBS = [("rd", "Rd"), ("s0", "You"), ("s1", "West"), ("s2", "North"), ("s3", "East"),
             ("p0", "Us"), ("p1", "Them"), ("t0", "Us"), ("t1", "Them"),
             ("g0", "Us"), ("g1", "Them"), ("b0", "Us"), ("b1", "Them")]
GOOD, BAD, AMBER = (125, 235, 150), (255, 135, 125), (255, 205, 90)


def history_sections(app):
    secs = []
    g = app.game
    if g is not None and g.rounds and not g.recorded:
        secs.append({"title": "Current match", "sub": f"in progress  -  first to {g.target}",
                     "rounds": g.rounds, "final": list(g.scores), "result": None})
    for m in reversed(app.matches):
        won = m["winner"] == 0
        secs.append({"title": f"Match {m.get('n', '?')}",
                     "sub": f"{m.get('when', '')}  -  first to {m.get('target', '?')}  -  "
                            f"partner {m.get('partner', '?')}, opponents {m.get('opponents', '?')}",
                     "rounds": m["rounds"], "final": m["final"],
                     "result": ("You won", won)})
    return secs


def layout_history(secs):
    items, y = [], 0
    for sec in secs:
        items.append(("title", sec, y))
        y += 40
        items.append(("head", None, y))
        y += 50
        for i, rd in enumerate(sec["rounds"]):
            items.append(("round", (i, rd), y))
            y += 30
        items.append(("foot", sec, y))
        y += 34 + 24
    return items, y


def history_total_height(app):
    return layout_history(history_sections(app))[1]


def draw_history_cell(key, text, color, y, font=None):
    x, w = HIST_COL[key]
    draw_text(text, font or FONT_S, color, (x + w // 2, y), "center")


def draw_history(app, now, mouse):
    draw_felt()
    draw_button(BACK_RECT, "< Back", mouse, font=FONT_S)
    title = outlined_text("Match History", 54, (255, 255, 255), (8, 45, 22), 4)
    screen.blit(title, title.get_rect(center=(WIDTH // 2, 48)))
    legend = "Us = You + North        Them = West + East        * = bag penalty (-100)"
    draw_text(legend, FONT_S, (205, 235, 210), (WIDTH // 2, 96), "center")
    draw_panel(HIST_VIEW, 95, 14)

    secs = history_sections(app)
    if not secs:
        draw_text("No matches yet.", FONT_M, (255, 255, 255), (WIDTH // 2, 340), "center")
        draw_text("Play a game and every round will be listed here.", FONT_S, (205, 235, 210),
                  (WIDTH // 2, 380), "center")
        return

    items, total = layout_history(secs)
    max_scroll = max(0, total - HIST_VIEW.h + 10)
    app.history_scroll = max(0, min(max_scroll, app.history_scroll))
    screen.set_clip(HIST_VIEW)
    for kind, data, y in items:
        sy = HIST_VIEW.y + 8 + y - app.history_scroll
        if sy > HIST_VIEW.bottom or sy + 50 < HIST_VIEW.y:
            continue
        if kind == "title":
            r = draw_text(data["title"], FONT_M, (255, 215, 0), (50, sy + 4))
            draw_text(data["sub"], FONT_XS, (205, 235, 210), (r.right + 16, sy + 10))
            if data["result"]:
                won = data["result"][1]
                draw_text(f"{'You won' if won else 'You lost'}  {data['final'][0]} - {data['final'][1]}",
                          FONT_M, GOOD if won else BAD, (1026, sy + 4), "right")
        elif kind == "head":
            for label, x0, x1 in HIST_GROUPS:
                draw_text(label, FONT_XS, (255, 255, 255), ((x0 + x1) // 2, sy), "center")
                pygame.draw.line(screen, (150, 190, 160), (x0 + 6, sy + 20), (x1 - 6, sy + 20), 1)
            for key, label in HIST_SUBS:
                draw_history_cell(key, label, (205, 235, 210), sy + 24, FONT_XS)
        elif kind == "round":
            i, rd = data
            if i % 2 == 0:
                draw_panel(pygame.Rect(46, sy - 3, 984, 28), 55, 6)
            draw_history_cell("rd", str(i + 1), (255, 255, 255), sy)
            for seat in range(4):
                draw_history_cell(f"s{seat}", f"{bid_text(rd['bids'][seat])} / {rd['tricks'][seat]}",
                                  (255, 255, 255), sy)
            for team in (0, 1):
                pts = rd["points"][team]
                draw_history_cell(f"p{team}", f"{pts:+d}", GOOD if pts >= 0 else BAD, sy)
                draw_history_cell(f"t{team}", str(rd["scores"][team]), (255, 255, 255), sy)
                gained = rd["bags_gained"][team]
                mark = "*" if rd["penalty"][team] else ""
                draw_history_cell(f"g{team}", f"+{gained}{mark}" if gained else "-",
                                  AMBER if gained else (150, 175, 155), sy)
                draw_history_cell(f"b{team}", str(rd["bags"][team]), (255, 255, 255), sy)
        elif kind == "foot":
            f0, f1 = data["final"]
            label = "Score so far" if data["result"] is None else "Final score"
            pygame.draw.line(screen, (150, 190, 160), (50, sy + 2), (1026, sy + 2), 1)
            draw_text(f"{label}:   Your team {f0}   -   Opponents {f1}", FONT_S, (255, 255, 255),
                      (WIDTH // 2, sy + 8), "center")
    screen.set_clip(None)

    track = pygame.Rect(HIST_VIEW.right + 6, HIST_VIEW.y, 14, HIST_VIEW.h)
    draw_panel(track, 90, 7)
    if max_scroll > 0:
        thumb_h = max(36, int(track.h * HIST_VIEW.h / (total + 10)))
        thumb_y = track.y + int((track.h - thumb_h) * app.history_scroll / max_scroll)
        pygame.draw.rect(screen, (230, 230, 220), (track.x, thumb_y, track.w, thumb_h), border_radius=7)
        draw_text("scroll with the mouse wheel or arrow keys", FONT_XS, (170, 205, 180),
                  (WIDTH // 2, HIST_VIEW.bottom + 10), "center")


HIST_TRACK = pygame.Rect(HIST_VIEW.right + 6, HIST_VIEW.y, 14, HIST_VIEW.h)


# ----------------------------- App (screens) ------------------------
class App:
    """Ties the screens together: menu, options, match history and the game."""

    def __init__(self, now=0):
        data = load_save()
        s = dict(DEFAULT_SETTINGS)
        raw = data.get("settings") if isinstance(data.get("settings"), dict) else {}
        if raw.get("partner") in LEVELS:
            s["partner"] = raw["partner"]
        if raw.get("opponents") in LEVELS:
            s["opponents"] = raw["opponents"]
        if raw.get("target") in TARGETS:
            s["target"] = raw["target"]
        if raw.get("style") in [st["name"] for st in STYLES]:
            s["style"] = raw["style"]
        self.settings = s
        raw_matches = data.get("matches") if isinstance(data.get("matches"), list) else []
        self.matches = [m for m in raw_matches if valid_match(m)][-MAX_MATCHES:]
        self.game = None
        self.screen = "menu"
        self.history_from = "menu"
        self.history_scroll = 0
        self.quit = False
        apply_style(s["style"])

    # ---- helpers ----
    def resumable(self):
        return self.game is not None and not self.game.finished

    def save(self):
        write_save(self.settings, self.matches)

    def new_game(self, now):
        self.game = Game(now, self.settings)
        self.screen = "game"

    def open_history(self, came_from):
        self.history_from = came_from
        self.history_scroll = 0
        self.screen = "history"

    def go_back(self):
        if self.screen == "history":
            back = self.history_from
            self.screen = "game" if back == "game" and self.game is not None else "menu"
        elif self.screen in ("options", "game"):
            self.screen = "menu"

    # ---- input ----
    def handle_click(self, pos, now):
        if self.screen == "menu":
            items = menu_items(self.resumable())
            for (key, _), rect in zip(items, menu_rects(items)):
                if rect.collidepoint(pos):
                    if key == "resume":
                        self.screen = "game"
                    elif key == "new":
                        self.new_game(now)
                    elif key == "options":
                        self.screen = "options"
                    elif key == "history":
                        self.open_history("menu")
                    elif key == "quit":
                        self.quit = True
                    return
        elif self.screen == "options":
            self.click_options(pos)
        elif self.screen == "history":
            if BACK_RECT.collidepoint(pos):
                self.go_back()
            elif HIST_TRACK.collidepoint(pos):
                limit = max(0, history_total_height(self) - HIST_VIEW.h + 10)
                frac = (pos[1] - HIST_TRACK.y) / HIST_TRACK.h
                self.history_scroll = int(max(0, min(1, frac)) * limit)
        elif self.screen == "game" and self.game is not None:
            g = self.game
            if g.phase == "hand_over" and g.finished:
                for key, rect in zip(("again", "menu", "history"), match_over_rects()):
                    if rect.collidepoint(pos):
                        if key == "again":
                            self.new_game(now)
                        elif key == "menu":
                            self.screen = "menu"
                        else:
                            self.open_history("game")
                        return
            elif GAME_MENU_RECT.collidepoint(pos):
                self.screen = "menu"
            elif GAME_HISTORY_RECT.collidepoint(pos):
                self.open_history("game")
            else:
                g.handle_click(pos, now)

    def click_options(self, pos):
        if BACK_RECT.collidepoint(pos):
            self.screen = "menu"
            return
        changed = False
        for key, y, values in (("partner", OPT_PARTNER_Y, LEVELS), ("opponents", OPT_OPP_Y, LEVELS),
                               ("target", OPT_TARGET_Y, TARGETS)):
            for value, rect in zip(values, seg_rects(OPT_SEG_X, y, len(values))):
                if rect.collidepoint(pos):
                    self.settings[key] = value
                    changed = True
        for style, rect in zip(STYLES, style_cell_rects(len(STYLES))):
            if rect.collidepoint(pos):
                self.settings["style"] = style["name"]
                apply_style(style["name"])
                changed = True
        if changed:
            self.save()

    def handle_wheel(self, dy):
        if self.screen == "history":
            self.history_scroll = max(0, self.history_scroll - dy * 60)

    def handle_key(self, key, now):
        if key == pygame.K_ESCAPE:
            self.go_back()
        elif self.screen == "history":
            step = {pygame.K_UP: -45, pygame.K_DOWN: 45, pygame.K_PAGEUP: -400,
                    pygame.K_PAGEDOWN: 400}.get(key)
            if step is not None:
                self.history_scroll = max(0, self.history_scroll + step)
            elif key == pygame.K_HOME:
                self.history_scroll = 0
            elif key == pygame.K_END:
                self.history_scroll = 10 ** 6   # clamped when drawn

    # ---- timing and drawing ----
    def update(self, now):
        if self.screen != "game" or self.game is None:
            return
        g = self.game
        g.update(now)
        if g.finished and not g.recorded and g.phase == "hand_over":
            g.recorded = True
            number = max([m.get("n", 0) for m in self.matches] + [0]) + 1
            self.matches.append(g.match_record(number))
            self.matches = self.matches[-MAX_MATCHES:]
            self.save()

    def draw(self, now, mouse):
        if self.screen == "menu":
            draw_menu(self, now, mouse)
        elif self.screen == "options":
            draw_options(self, now, mouse)
        elif self.screen == "history":
            draw_history(self, now, mouse)
        elif self.game is not None:
            draw(self.game, now, mouse)


# ----------------------------- Main loop ----------------------------
def main():
    init_graphics()
    clock = pygame.time.Clock()
    app = App(pygame.time.get_ticks())

    while not app.quit:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                app.quit = True
            elif event.type == pygame.KEYDOWN:
                app.handle_key(event.key, now)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                app.handle_click(event.pos, now)
            elif event.type == pygame.MOUSEWHEEL:
                app.handle_wheel(event.y)
        app.update(now)
        app.draw(now, pygame.mouse.get_pos())
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
