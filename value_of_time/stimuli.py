"""Stimuli for the value-of-time survey: one fixed persona, a fact library, and ten survey questions.

Design rules
- The persona contains NO information about income, prices, or time trade-offs. Every money/time signal
  lives in the fact slot so it can be switched on and off.
- Every fact contains the numbers needed to compute an implied dollars-per-hour value, and the facts imply
  *different* values, so a numeric answer can be traced back to the fact it came from.
- Most facts are one-sided bounds (a revealed choice says "at least" or "at most"), only the wage is a point.
- Every question asks for a natural dollar amount; `hours` converts it to an implied $/hour.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PERSONA = (
    "You are Sam, a 31-year-old who shares an apartment with your partner, Jordan, and a rescue dog named Pepper. "
    "On weekday evenings you like cooking, watching basketball, and calling your sister. "
    "On weekends you play in a recreational soccer league, see friends, and now and then take a trip. "
    "People describe you as friendly."
)


@dataclass(frozen=True)
class Fact:
    id: str
    text: str
    domain: str              # work | travel | leisure | chores | errands
    bound: str               # point | lower | upper  (on the value of an hour)
    implied_hourly: float    # $/hour implied by the fact
    derivation: str
    mixed_motive: bool       # True if the choice plausibly reflects things other than time (fun, status, a date)
    keywords: tuple[str, ...] = field(default_factory=tuple)  # regexes for detecting the fact in a thinking trace


FACTS: tuple[Fact, ...] = (
    Fact("A", "You work full-time as an office coordinator and earn $40,000 a year before taxes.",
         "work", "point", 19.23, "$40,000 / 2,080 hours", False,
         (r"40,?000", r"\bsalary\b", r"\bwage\b", r"office coordinator", r"19\.2")),
    Fact("B", "Last night you chose Lyft's \"Wait & Save\" option: you waited an extra 8 minutes for your ride to save $4.",
         "travel", "upper", 30.00, "$4 / (8/60 h): waiting was worth it, so an hour is worth at most $30", False,
         (r"lyft", r"wait\s*(&|and)\s*save", r"8 (extra )?minutes")),
    Fact("C", "On a trip to Disneyland last month, you paid $30 for a skip-the-line pass that saved you about 2 hours of waiting over the day.",
         "leisure", "lower", 15.00, "$30 / 2 h: paying was worth it, so an hour is worth at least $15", True,
         (r"disney", r"skip[- ]the[- ]line pass", r"lightning lane")),
    Fact("D", "On your commute to work you take a toll road that costs $9 and saves you about 15 minutes compared with the free route.",
         "travel", "lower", 36.00, "$9 / (15/60 h): at least $36/h", False,
         (r"\btoll", r"\$9\b", r"commute")),
    Fact("E", "Last weekend downtown you circled the block for 20 minutes looking for free street parking instead of paying $15 for a garage.",
         "errands", "upper", 45.00, "$15 / (20/60 h): at most $45/h", False,
         (r"circl", r"street parking", r"garage")),
    Fact("F", "On a date last night you paid $35 to valet the car, which saved you about 10 minutes of looking for parking.",
         "leisure", "lower", 210.00, "$35 / (10/60 h): at least $210/h", True,
         (r"valet", r"\$35\b", r"\bdate\b")),
    Fact("G", "Last month your manager offered you an extra Saturday shift at time-and-a-half, about $29 an hour, and you turned it down.",
         "work", "lower", 28.85, "declined $28.85/h (pre-tax) for a free Saturday: leisure hour worth at least ~$29", False,
         (r"saturday shift", r"time[- ]and[- ]a[- ]half", r"\$29\b", r"turned (it )?down")),
    Fact("H", "You pay a cleaner $60 to clean your apartment, a job that would take you about 3 hours yourself.",
         "chores", "lower", 20.00, "$60 / 3 h: at least $20/h", False,
         (r"cleaner", r"\$60\b", r"clean(ing)? (the|your) apartment")),
    Fact("I", "Yesterday you drove 10 extra minutes to a cheaper gas station to save $3 on a fill-up.",
         "errands", "upper", 18.00, "$3 / (10/60 h): at most $18/h", False,
         (r"gas station", r"fill-?up", r"\$3\b")),
)
FACT_BY_ID = {f.id: f for f in FACTS}


@dataclass(frozen=True)
class Question:
    id: str
    domain: str              # general | work | travel | leisure | chores | errands | social
    direction: str           # WTP (pay to save time) | WTA (accept money to give up time)
    text: str
    hours: float             # implied $/h = answer / hours
    hypothesized_facts: tuple[str, ...]  # facts we expect to "fit" this question (a hypothesis, not a key)


QUESTIONS: tuple[Question, ...] = (
    Question("general", "general", "neutral",
             "In general, how much is one hour of your time worth to you, in dollars?", 1.0, ("A",)),
    Question("weekend_gig", "work", "WTA",
             "A local business offers you a one-time, 4-hour job this Saturday. What is the lowest total payment you would accept to do it?",
             4.0, ("A", "G")),
    Question("research_study", "work", "WTA",
             "A university researcher invites you to a 1-hour study on a weekday evening. What is the lowest payment you would accept to take part?",
             1.0, ("A", "G")),
    Question("nonstop_flight", "travel", "WTP",
             "You are booking a flight home to see your family for the holidays. A nonstop flight saves 3 hours compared with a one-stop flight. What is the most extra you would pay for the nonstop?",
             3.0, ("B", "D")),
    Question("priority_pickup", "travel", "WTP",
             "You are ordering a rideshare. A \"Priority Pickup\" option gets a driver to you 10 minutes sooner. What is the most extra you would pay for it?",
             10 / 60, ("B", "D")),
    Question("grocery_delivery", "errands", "WTP",
             "Grocery delivery would save you a 1-hour trip to the store. What is the most you would pay in delivery fees and tip combined?",
             1.0, ("E", "I", "H")),
    Question("furniture_assembly", "chores", "WTP",
             "You bought a bookshelf that takes about 2 hours to assemble. What is the most you would pay someone to assemble it for you?",
             2.0, ("H",)),
    Question("theme_park", "leisure", "WTP",
             "At an amusement park, a skip-the-line pass would save you about 2 hours of waiting over the day. What is the most you would pay for it?",
             2.0, ("C",)),
    Question("train_delay", "travel", "WTA",
             "Your train is delayed 5 hours because of the operator's error. What compensation would fully make up for the lost time?",
             5.0, ("B", "D")),
    Question("volunteer_or_donate", "social", "neutral",
             "A local charity asks you to volunteer for 2 hours this weekend; you could donate money instead. What donation would feel equivalent to giving the 2 hours?",
             2.0, ("A",)),
)
QUESTION_BY_ID = {q.id: q for q in QUESTIONS}
