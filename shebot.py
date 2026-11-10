"""SheBot: a small rule-based help assistant.

It matches keywords to answers. To make it smarter later, replace `shebot_reply`
with a call to an LLM and keep the same return shape: {"reply": str, "suggestions": [str]}.
"""
import re

DEFAULT_SUGGESTIONS = ["How do I book a ride?", "How do I offer a ride?", "Safety tips", "Emergency"]

# Ordered by priority: emergency must always win.
INTENTS = [
    {
        "keywords": ["emergency", "sos", "danger", "unsafe now", "help me", "attack", "harass", "scared"],
        "reply": ("🚨 If you are in danger right now, call 999 (Bangladesh National Emergency Service) "
                  "immediately. Share your live location with a trusted contact, move to a crowded, "
                  "well-lit place, and report the user from the ride page once you are safe. "
                  "For violence against women, you can also call the 109 helpline."),
        "suggestions": ["Safety tips", "How do I report someone?"],
    },
    {
        "keywords": ["report", "block", "complain"],
        "reply": ("To report someone, open the ride page or chat and contact support (demo: "
                  "support@sheride.example). Reports are reviewed within 24 hours, and accounts that "
                  "break the community guidelines are suspended."),
        "suggestions": ["Safety tips", "Emergency"],
    },
    {
        "keywords": ["safe", "safety", "tips", "trust"],
        "reply": ("Safety tips:\n• Only ride with ✓ verified members.\n• Keep all communication in the "
                  "SheRide chat; your phone number stays private.\n• Check that the car model and colour "
                  "match the ride details before you get in.\n• Share your trip with a friend or family member.\n"
                  "• Trust your instincts: you can cancel anytime."),
        "suggestions": ["Emergency", "How does verification work?"],
    },
    {
        "keywords": ["men", "man", "male", "husband", "boyfriend", "brother", "son", "who can", "women only",
                     "women-only", "join sheride"],
        "reply": ("SheRide is women-only: every ride sharer and every passenger is a verified woman. "
                  "Men can't create accounts or ride along, so please book only for yourself."),
        "suggestions": ["How does verification work?", "How do I book a ride?"],
    },
    {
        "keywords": ["chat", "contact", "message", "talk", "call", "phone", "number"],
        "reply": ("Each seat request gets a private chat between the ride sharer and the passenger. "
                  "Open it from “My trips” or the ride page. Quick replies like “I'm at the pickup point” "
                  "make coordinating easy. Phone numbers are never shown publicly."),
        "suggestions": ["Safety tips", "How do I book a ride?"],
    },
    {
        "keywords": ["book", "find", "join", "seat", "search", "passenger", "request"],
        "reply": ("To book: go to “Find a ride”, search by where you're leaving from and where you're going, "
                  "open a ride and tap “Request seat”. A private chat with the ride sharer opens right away. "
                  "Your seat is confirmed once she accepts."),
        "suggestions": ["How do I chat with the driver?", "How do I cancel?"],
    },
    {
        "keywords": ["offer", "share my", "post", "driver", "drive", "create ride", "ride sharer"],
        "reply": ("To offer a ride: tap “Offer a ride”, enter your route, departure time, free seats, "
                  "fare per seat and your vehicle. Seat requests appear on your ride page, where you can "
                  "accept, decline or chat with each passenger."),
        "suggestions": ["How much should I charge?", "How do I chat with the driver?"],
    },
    {
        "keywords": ["cancel"],
        "reply": ("Passengers can cancel from the ride page or “My trips”. Ride sharers can cancel the "
                  "whole ride from the ride page, and every passenger is notified in their chat. "
                  "Please cancel early so others can plan."),
        "suggestions": ["How do I book a ride?"],
    },
    {
        "keywords": ["fare", "price", "pay", "cost", "money", "charge", "bkash", "cash"],
        "reply": ("The ride sharer sets the fare per seat when she posts the ride; it is meant to share "
                  "fuel and toll costs, not to make a profit. In this demo, passengers pay the ride sharer "
                  "directly (cash or bKash) after the trip."),
        "suggestions": ["How do I offer a ride?"],
    },
    {
        "keywords": ["verify", "verification", "nid", "id card", "identity", "verified"],
        "reply": ("Every member verifies with her National ID and a selfie check before she can offer, "
                  "book or chat. This keeps SheRide women-only. (In this demo, verification is approved "
                  "automatically.)"),
        "suggestions": ["Who can join SheRide?", "Safety tips"],
    },
    {
        "keywords": ["hi", "hello", "hey", "salam", "assalamu", "good morning", "good evening"],
        "reply": ("Hi! 🌸 I'm SheBot, your SheRide assistant. I can help you book or offer a ride, "
                  "explain how chat and verification work, or share safety tips. What do you need?"),
        "suggestions": DEFAULT_SUGGESTIONS,
    },
    {
        "keywords": ["thank", "thanks", "dhonnobad"],
        "reply": "You're welcome! Have a safe trip 🌸",
        "suggestions": DEFAULT_SUGGESTIONS,
    },
]


def _matches(text, keyword):
    # Whole-word match for short keywords ("hi", "man") so "this" or "woman" don't trigger them.
    if len(keyword) <= 4 and " " not in keyword:
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
    return keyword in text


def shebot_reply(message, logged_in=False):
    text = (message or "").lower()
    if not text:
        return {"reply": "Ask me anything about SheRide 🌸", "suggestions": DEFAULT_SUGGESTIONS}
    for intent in INTENTS:
        if any(_matches(text, k) for k in intent["keywords"]):
            reply = intent["reply"]
            if not logged_in and intent["keywords"][0] in ("book", "offer"):
                reply += "\n\nYou'll need to join and verify first. Tap “Join” at the top."
            return {"reply": reply, "suggestions": intent["suggestions"]}
    return {
        "reply": ("Sorry, I didn't quite get that. I can help with booking, offering rides, chat, "
                  "cancellations, fares, verification and safety."),
        "suggestions": DEFAULT_SUGGESTIONS,
    }
