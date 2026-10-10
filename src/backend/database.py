"""
MongoDB database configuration and setup for Mergington High School API
"""

import copy
import logging

from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from argon2 import PasswordHasher, exceptions as argon2_exceptions


class InMemoryCollection:
    """Minimal collection implementation used when MongoDB is unavailable."""

    def __init__(self, initial=None):
        self._documents = {}
        if initial:
            for document in initial:
                self._documents[document.get("_id")] = document

    def _matches(self, document, query):
        if not query:
            return True

        for key, expected in query.items():
            value = document
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value:
                    value = None
                    break
                value = value[part]

            if isinstance(expected, dict):
                for operator, operand in expected.items():
                    if operator == "$in":
                        matches = (
                            any(item in operand for item in value)
                            if isinstance(value, list)
                            else value in operand
                        )
                        if not matches:
                            return False
                    elif operator == "$gte" and (
                        value is None or value < operand
                    ):
                        return False
                    elif operator == "$lte" and (
                        value is None or value > operand
                    ):
                        return False
            elif value != expected:
                return False
        return True

    def count_documents(self, query=None):
        query = query or {}
        return sum(1 for doc in self._documents.values() if self._matches(doc, query))

    def find(self, query=None):
        query = query or {}
        for doc in self._documents.values():
            if self._matches(doc, query):
                yield dict(doc)

    def find_one(self, query=None):
        query = query or {}
        for doc in self._documents.values():
            if self._matches(doc, query):
                return dict(doc)
        return None

    def insert_one(self, document):
        document_id = document.get("_id")
        self._documents[document_id] = dict(document)
        return type("InsertOneResult", (), {"inserted_id": document_id})()

    def update_one(self, query, update):
        doc = self.find_one(query)
        if doc is None:
            return type("UpdateResult", (), {"modified_count": 0})()

        stored = self._documents.get(doc["_id"], {})
        for operation, payload in update.items():
            if operation == "$push":
                for key, value in payload.items():
                    items = stored.setdefault(key, [])
                    if value not in items:
                        items.append(value)
            elif operation == "$pull":
                for key, value in payload.items():
                    items = stored.get(key, [])
                    stored[key] = [item for item in items if item != value]

        self._documents[doc["_id"]] = stored
        return type("UpdateResult", (), {"modified_count": 1})()

    def aggregate(self, pipeline):
        def get_value(document, path):
            value = document
            for part in path.split("."):
                if not isinstance(value, dict):
                    return None
                value = value.get(part)
            return value

        def set_value(document, path, value):
            parts = path.split(".")
            target = document
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value

        docs = [copy.deepcopy(doc) for doc in self._documents.values()]
        for stage in pipeline:
            if "$unwind" in stage:
                field = stage["$unwind"].lstrip("$")
                flat = []
                for doc in docs:
                    value = get_value(doc, field)
                    if isinstance(value, list):
                        for item in value:
                            next_doc = copy.deepcopy(doc)
                            set_value(next_doc, field, item)
                            flat.append(next_doc)
                docs = flat
            elif "$group" in stage:
                key_field = stage["$group"]["_id"]
                path = key_field.lstrip("$") if isinstance(key_field, str) else None
                keys = []
                for doc in docs:
                    key = get_value(doc, path) if path else key_field
                    if key not in keys:
                        keys.append(key)
                docs = [{"_id": key} for key in keys]
            elif "$sort" in stage:
                sort_by = stage["$sort"]
                field, direction = next(iter(sort_by.items()))
                docs = sorted(
                    docs,
                    key=lambda doc: doc.get(field),
                    reverse=direction < 0,
                )
        return docs


# Connect to MongoDB when available; otherwise fall back to an in-memory store.
try:
    client = MongoClient(
        "mongodb://localhost:27017/",
        serverSelectionTimeoutMS=2000,
    )
    client.admin.command('ping')
    db = client['mergington_high']
    activities_collection = db['activities']
    teachers_collection = db['teachers']
except ServerSelectionTimeoutError as error:
    logging.getLogger(__name__).warning(
        "MongoDB is unavailable; using in-memory storage: %s",
        error,
    )
    activities_collection = InMemoryCollection()
    teachers_collection = InMemoryCollection()

# Methods
def hash_password(password):
    """Hash password using Argon2"""
    ph = PasswordHasher()
    return ph.hash(password)


def verify_password(hashed_password: str, plain_password: str) -> bool:
    """Verify a plain password against an Argon2 hashed password.

    Returns True when the password matches, False otherwise.
    """
    ph = PasswordHasher()
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except argon2_exceptions.VerifyMismatchError:
        return False
    except Exception:
        # For any other exception (e.g., invalid hash), treat as non-match
        return False

def init_database():
    """Initialize database if empty"""

    # Initialize activities if empty
    if activities_collection.count_documents({}) == 0:
        for name, details in initial_activities.items():
            activities_collection.insert_one({"_id": name, **details})

    # Initialize teacher accounts if empty
    if teachers_collection.count_documents({}) == 0:
        for teacher in initial_teachers:
            teachers_collection.insert_one({"_id": teacher["username"], **teacher})

# Initial database if empty
initial_activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Mondays and Fridays, 3:15 PM - 4:45 PM",
        "schedule_details": {
            "days": ["Monday", "Friday"],
            "start_time": "15:15",
            "end_time": "16:45"
        },
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 7:00 AM - 8:00 AM",
        "schedule_details": {
            "days": ["Tuesday", "Thursday"],
            "start_time": "07:00",
            "end_time": "08:00"
        },
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Morning Fitness": {
        "description": "Early morning physical training and exercises",
        "schedule": "Mondays, Wednesdays, Fridays, 6:30 AM - 7:45 AM",
        "schedule_details": {
            "days": ["Monday", "Wednesday", "Friday"],
            "start_time": "06:30",
            "end_time": "07:45"
        },
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 5:30 PM",
        "schedule_details": {
            "days": ["Tuesday", "Thursday"],
            "start_time": "15:30",
            "end_time": "17:30"
        },
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and compete in basketball tournaments",
        "schedule": "Wednesdays and Fridays, 3:15 PM - 5:00 PM",
        "schedule_details": {
            "days": ["Wednesday", "Friday"],
            "start_time": "15:15",
            "end_time": "17:00"
        },
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore various art techniques and create masterpieces",
        "schedule": "Thursdays, 3:15 PM - 5:00 PM",
        "schedule_details": {
            "days": ["Thursday"],
            "start_time": "15:15",
            "end_time": "17:00"
        },
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 3:30 PM - 5:30 PM",
        "schedule_details": {
            "days": ["Monday", "Wednesday"],
            "start_time": "15:30",
            "end_time": "17:30"
        },
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and prepare for math competitions",
        "schedule": "Tuesdays, 7:15 AM - 8:00 AM",
        "schedule_details": {
            "days": ["Tuesday"],
            "start_time": "07:15",
            "end_time": "08:00"
        },
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 3:30 PM - 5:30 PM",
        "schedule_details": {
            "days": ["Friday"],
            "start_time": "15:30",
            "end_time": "17:30"
        },
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "amelia@mergington.edu"]
    },
    "Weekend Robotics Workshop": {
        "description": "Build and program robots in our state-of-the-art workshop",
        "schedule": "Saturdays, 10:00 AM - 2:00 PM",
        "schedule_details": {
            "days": ["Saturday"],
            "start_time": "10:00",
            "end_time": "14:00"
        },
        "max_participants": 15,
        "participants": ["ethan@mergington.edu", "oliver@mergington.edu"]
    },
    "Science Olympiad": {
        "description": "Weekend science competition preparation for regional and state events",
        "schedule": "Saturdays, 1:00 PM - 4:00 PM",
        "schedule_details": {
            "days": ["Saturday"],
            "start_time": "13:00",
            "end_time": "16:00"
        },
        "max_participants": 18,
        "participants": ["isabella@mergington.edu", "lucas@mergington.edu"]
    },
    "Sunday Chess Tournament": {
        "description": "Weekly tournament for serious chess players with rankings",
        "schedule": "Sundays, 2:00 PM - 5:00 PM",
        "schedule_details": {
            "days": ["Sunday"],
            "start_time": "14:00",
            "end_time": "17:00"
        },
        "max_participants": 16,
        "participants": ["william@mergington.edu", "jacob@mergington.edu"]
    }
}

initial_teachers = [
    {
        "username": "mrodriguez",
        "display_name": "Ms. Rodriguez",
        "password": hash_password("art123"),
        "role": "teacher"
     },
    {
        "username": "mchen",
        "display_name": "Mr. Chen",
        "password": hash_password("chess456"),
        "role": "teacher"
    },
    {
        "username": "principal",
        "display_name": "Principal Martinez",
        "password": hash_password("admin789"),
        "role": "admin"
    }
]
