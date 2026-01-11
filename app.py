import csv
import datetime as dt
import math
from pathlib import Path
import random
from string import ascii_letters, digits

from dateutil import tz
from dateutil.parser import parse
from flask import Flask, render_template, request


SECONDS_PER_YEAR = 31536000
NUM_TRIES = 100

ALLOWED = set(ascii_letters + digits + "-")

NOW_MARKER = "now"


class Event:
    def __init__(self, description: str, date: dt.datetime):
        self.description = description
        self.date = date
        self.url = self._make_url()

    def _make_url(self):
        desc = self.description.lower().replace(" ", "-")
        url = "".join([c for c in desc if c in ALLOWED])
        return url[:40]

    @property
    def datestr(self) -> str:
        return self.date.strftime("%-d %B, %Y")

    def __lt__(self, other) -> bool:
        return self.date < other.date

    def __sub__(self, other) -> dt.datetime:
        return self.date - other.date

    def __repr__(self) -> str:
        return self.description

    @staticmethod
    def now():
        return Event(NOW_MARKER, dt.datetime.now(tz.tzlocal()))


class TimeghostCreationError(ValueError):
    """Creation error"""


class TimeghostValidationError(ValueError):
    """Validation error"""


class Timeghost:
    def __init__(
        self,
        first: Event,
        middle: Event,
        last: Event,
        check: bool = True,
    ):
        self.first = first
        self.middle = middle
        self.last = last
        self.tries = 1
        if check:
            if not self.is_valid():
                raise TimeghostValidationError(f"Invalid Timeghost: {self}")

    @property
    def first_gap(self) -> dt.timedelta:
        """Time difference between the middle and first event"""
        return self.middle - self.first

    @property
    def first_gap_years(self) -> dt.timedelta:
        """Time difference between the middle and first event in years"""
        return self.first_gap.total_seconds() / SECONDS_PER_YEAR

    @property
    def last_gap(self) -> dt.timedelta:
        """Time difference between the last and middle event"""
        return self.last - self.middle

    @property
    def last_gap_years(self) -> dt.timedelta:
        """Time difference between the last and middle event in years"""
        return self.last_gap.total_seconds() / SECONDS_PER_YEAR

    @property
    def permalink_url(self) -> str:
        return f"/{self.first.url}/{self.middle.url}/{self.last.url}"

    def is_valid(self) -> bool:
        """Verify that this timeghost is valid"""
        is_right_order = self.first < self.middle < self.last
        is_right_closeness = self.first_gap < self.last_gap
        return is_right_order and is_right_closeness

    def __repr__(self) -> str:
        """String representation"""
        validity = "is valid" if self.is_valid() else "is not valid"
        return (
            f"{self.middle} is closer to "
            f"({self.first_gap_years:.1f}) {self.first} than "
            f"({self.last_gap_years:.1f}) {self.last} "
            f"{validity}, {self.tries} trie(s)"
        )

    @property
    def factoid(self) -> str:
        last = "today" if self.last.description == NOW_MARKER else f"the {self.last}"
        return f"The {self.middle} is closer to the {self.first} than {last}."

    @property
    def start_of_haunting(self) -> dt.datetime:
        """The date that this timeghost because valid"""
        return self.middle.date + self.first_gap

    @property
    def verbose_factoid(self) -> str:
        if self.last.description == NOW_MARKER:
            last = "today"
            last_date = dt.datetime.now(tz.tzlocal()).strftime("%-d %B, %Y")
        else:
            last = f"the {self.last}"
            last_date = self.last.datestr

        # Adjust precision until printed dates are different:
        precision = 0
        while f"{self.first_gap_years:.{precision}f}" ==  f"{self.last_gap_years:.{precision}f}":
            precision += 1

        return (
            f"The {self.middle} ({self.middle.datestr}) "
            f"is closer ({self.first_gap_years:.{precision}f} years) to "
            f"the {self.first} ({self.first.datestr}) ({self.last_gap_years:.{precision}f} years) than "
            f"{last} ({last_date}) "
            #f"({self.is_valid()}, {self.tries} tries). "
        )

    @staticmethod
    def _event_before(middle, events) -> Event:
        """Get a random event that occurs earlier than the middle argument"""
        befores = [e for e in events if e < middle]
        return random.choice(befores)

    @staticmethod
    def _make(
        events: list[Event],
        first: Event = None,
        middle: Event = None,
        last: Event = None,
    ):
        """
        Create a timeghost object using two specified events, either the first
        and middle, or middle and last.  The remaining event will be selected
        based on the sorting of the events input -- random if that list is
        random, best- or worst-case if events is sorted.
        """

        find_first_mode = first is None and middle is not None and last is not None
        find_last_mode = first is not None and middle is not None and last is None

        if find_first_mode:
            invalid_event_check = lambda f: f > middle
            tg_events = lambda f: (f, middle, last)
        elif find_last_mode:
            invalid_event_check = lambda l: l < middle
            tg_events = lambda l: (first, middle, l)
        else:
            raise TimeghostCreationError(
                f"invalid Event specification: {first}, {middle}, {last}."
            )

        for event in events:
            if invalid_event_check(event):
                continue
            try:
                return Timeghost(*tg_events(event))
            except TimeghostValidationError:
                pass
        raise TimeghostCreationError(
            "Can't create timeghost with Event specification: {first}, {middle}, {last}."
        )

    @staticmethod
    def make(events, middle, is_now, is_random):
        """
        Make a timeghost with optional specified middle event
        If middle is not specified, pick a random middle event
        """
        if is_random:
            random.shuffle(events)
        else:
            events.sort()

        for i in range(NUM_TRIES):
            if middle is None:
                middle = random.choice(events)
            if middle in events:
                events.remove(middle)
            try:
                if is_now:
                    first = None
                    last = Event.now()
                else:
                    first = Timeghost._event_before(middle, events)
                    last = None
                timeghost = Timeghost._make(events, first, middle, last)

                timeghost.tries = i + 1
                return timeghost
            except TimeghostCreationError:
                pass
        return timeghost


def load_events():
    """Load the database of available events"""
    # TODO GET the csv from /static/events?
    csv_file_path = Path(app.root_path) / "static/events_timeghost.csv"
    with open(csv_file_path) as csvfile:
        reader = csv.DictReader(csvfile)
        events = []
        for row in reader:
            description = row["description"]
            date = parse(row["date"])
            event = Event(description, date)
            events.append(event)
    return events


def load_specific_events(urls: list[str]) -> list[Event]:
    """Load specific events by their URLs"""
    all_events = load_events()
    events = []
    for url in urls:
        if url == NOW_MARKER:
            events.append(Event.now())
            continue
        for event in all_events:
            if event.url == url:
                events.append(event)
                break
    return events


def load_events_and_make_timeghost(is_random=False, middle=None, is_now=True):
    """Make a timeghost from the list of events"""
    events = load_events()
    try:
        tg = Timeghost.make(events, middle, is_now, is_random)
        return tg
    except TimeghostCreationError as e:
        return f"Can't make timeghost {e}"


app = Flask(
    __name__,
    template_folder=Path(__file__).resolve().parent / "templates/",
    static_url_path="/static",
)


@app.route("/pick", methods=["GET", "POST"])
def pick():
    """Pick a timeghost, or render a picked timeghost"""

    # pick a timeghost
    if request.method == "GET":
        events = load_events()
        events.sort(reverse=True)
        return render_template("pick.html", events=events)

    # render a picked timeghost
    if request.method == "POST":
        url_first = request.form["event_first"]
        url_middle = request.form["event_middle"]
        first, middle = load_specific_events([url_first, url_middle])

        tg = Timeghost(first, middle, Event.now(), check=False)
        return render_template("timeghost.html", timeghost=tg)


@app.route("/raves")
def raves():
    return render_template("raves.html")


@app.route("/worst/random")
def display_timeghost_random_optimized():
    """'last' =  now"""
    tg = load_events_and_make_timeghost()
    return render_template("timeghost.html", timeghost=tg)


@app.route("/random/random")
def display_timeghost_random_random():
    """'last' =  now"""
    tg = load_events_and_make_timeghost(is_random=True)
    return render_template("timeghost.html", timeghost=tg)


@app.route("/arbitrary/worst/random")
def display_timeghost_arbitrary_random_optimized():
    """from any arbitrary point, not last=now"""
    tg = load_events_and_make_timeghost(is_now=False)
    return render_template("timeghost.html", timeghost=tg)


@app.route("/arbitrary/random/random")
def display_timeghost_arbitrary_random_random():
    """from any arbitrary point, not last=now"""
    tg = load_events_and_make_timeghost(is_random=True, is_now=False)
    return render_template("timeghost.html", timeghost=tg)


@app.route("/worst/<event_url>")
def display_timeghost_worst(event_url):
    """'last' =  now"""
    event = load_specific_events([event_url])
    tg = load_events_and_make_timeghost(is_random=False, middle=event[0])
    return render_template("timeghost.html", timeghost=tg)


@app.route("/random/<event_url>")
def display_timeghost_random(event_url):
    """'last' =  now"""
    event = load_specific_events([event_url])
    tg = load_events_and_make_timeghost(is_random=True, middle=event[0])
    return render_template("timeghost.html", timeghost=tg)


@app.route("/arbitrary/worst/<event_url>")
def display_timeghost_arbitrary_worst(event_url):
    """from any arbitrary point, not last=now"""
    event = load_specific_events([event_url])
    tg = load_events_and_make_timeghost(is_random=False, middle=event[0], is_now=False)
    return render_template("timeghost.html", timeghost=tg)


@app.route("/arbitrary/random/<event_url>")
def display_timeghost_arbitrary_random(event_url):
    """from any arbitrary point, not last=now"""
    event = load_specific_events([event_url])
    tg = load_events_and_make_timeghost(is_random=True, middle=event[0], is_now=False)
    return render_template("timeghost.html", timeghost=tg)


@app.route("/<first_url>/<middle_url>/<last_url>")
def display_timeghost_arbitrary_fully_specified(first_url, middle_url, last_url):
    """specify all  three events, don't check validity"""
    events = load_specific_events([first_url, middle_url, last_url])
    tg = Timeghost(events[0], events[1], events[2], check=False)  # plain constructor
    return render_template("timeghost.html", timeghost=tg)


@app.route("/")
def display_timeghost_default():
    return display_timeghost_random_optimized()


# TODO
#
#  <form action="/test" method="POST">
#    <!-- TODO: try https://pikaday.dbushell.com/ -->
#    <input id="datetime-input" name="datetime-input" type="datetime-local">
#    <input type="text" name="description" placeholder="Something happened"/>
#    <button class="button" type="submit" name="add">Add Event</button>
#  </form>
