import random
import pandas as pd

adjectives = [
    "smart", "eco-friendly", "social", "AI-powered", "blockchain-based", "augmented reality",
    "virtual reality", "fitness", "mental health", "language learning", "travel", "food",
    "music", "pet", "gamified", "sustainable", "charity", "finance", "education", "productivity",
    "fashion", "beauty", "wellness", "sleep", "meditation", "art", "photography", "video",
    "shopping", "weather", "news", "sports", "transportation", "navigation", "e-commerce",
    "marketplace", "crowdsourcing", "collaboration", "remote", "event", "ticketing", "live-streaming",
    "podcast", "book", "comic", "cooking", "recipe", "diet", "notebook", "investment",
    "reminder", "habit-tracking", "goal-setting", "journaling", "diary", "task", "note-taking",
    "drawing", "sketching", "3D modeling", "animation", "green", "recycling", "DIY", "home",
    "garden", "language", "translation", "voice", "speech", "sign language", "accessibility",
    "remote work", "interview", "career", "resume", "dating", "relationship",
    "childcare", "senior care", "medical", "telehealth", "therapy", "wellbeing", "sleep", "alarm",
    "time management", "calendar", "scheduler", "flashcard", "quiz", "exam", "study", "mind map"
]

nouns = [
    "tracker", "platform", "hub", "app", "service", "assistant", "tool", "community", "network",
    "coach", "mentor", "guide", "diary", "journal", "planner", "dashboard", "marketplace", "exchange",
    "map", "navigator", "scanner", "analyzer", "optimizer", "generator", "creator", "editor", "studio",
    "workshop", "game", "challenge", "quiz", "flashcard", "podcast", "streamer", "gallery", "showcase",
    "forum", "chat", "messenger", "social", "media", "video", "photo", "recipe", "kitchen", "garden",
    "fitness", "health", "therapy", "finance", "investment", "budget", "shopping", "market", "store",
    "ticket", "event", "schedule", "calendar", "alarm", "reminder", "notebook", "whiteboard", "mind map",
    "sketch", "canvas", "workout", "routine", "habit", "goal", "task", "note", "memo", "log", "tracker", "gay notebooks",
]

verbs = [
    "helps you plan", "tracks", "monitors", "manages", "optimizes", "automates", "connects you with",
    "teaches you", "guides you through", "supports", "builds", "creates", "generates", "curates",
    "analyzes", "reports on", "visualizes", "reminds you of", "alerts you about", "translates", "transcribes",
    "schedules", "books", "orders", "delivers", "tracks", "organizes", "syncs", "collaborates on", "scores",
    "reviews", "edits", "enhances", "customizes", "personalizes", "gamifies", "streamlines", "facilitates",
    "bridges", "connects", "levels up", "empowers", "inspires", "motivates", "vibes with",
    "matches you with", "helps you find", "lets you share", "lets you host", "turns photos into",
    "converts text to", "monetizes", "protects", "secures", "backs up", "optimizes", "balances"
]

qualifiers = [
    "but think about the gay notebooks", "make it beluga themed", "add bamboos", "sparkles", "with a VHS aesthetic",
    "inspired by quantum mechanics", "neumorphic buttons that ooze softly when pressed",
    "jelly-physics toggles that wobble on state change",
    "glitch-art transition effects between screens",
    "retro 8-bit pixel art overlays on modern layouts",
    "cyberpunk neon grid backgrounds with animated scanlines",
    "low-poly 3D UI elements that subtly rotate",
    "holographic UI with floating panels and light refractions",
    "hand-drawn sketch borders and icons, as if doodled in a notebook",
    "watercolor wash backgrounds that bleed between sections",
    "faux-leather textures on panels and cards",
    "paper-fold animations like virtual origami unfolding menus",
    "tape-sticker accents and washi-tape “stuck” notes for alerts",
    "Polaroid photo frames around content cards",
    "bullet-journal style dotted-grid layouts with colored pens",
    "kaleidoscope gradients that shift as you scroll",
    "astro-space theme with twinkling stars and comet trails",
    "retro VHS glitch static and scan-line noise effect",
    "Lego-block UI pieces that snap together on interaction",
    "circuit-board pattern overlays that glow with pulses",
    "steampunk gears that spin to indicate loading",
    "origami-folding panels that crease and unfold",
    "liquid metal morph icons that flow into new shapes",
    "solarized palette with subtle day/night shifting",
    "emoji rain confetti on success screens",
    "chromatic-aberration blur on header text",
    "interactive parallax layers that move with device tilt",
    "gradient mesh backgrounds that morph over time",
    "Lego-style minifig avatars for user profiles",
    "tattoo-flash illustration accents around buttons",
    "paper-tear dividers between sections",
    "stained-glass window panel effects with colored light beams",
    "hologram scan effect when toggling modes",
    "marble texture panels with subtle veining animations",
    "Morse-code blink notifications via pulsing dots and dashes",
    "pixelated VHS rewind effect on undo actions",
    "golden-ratio grid snap-to layouts for perfect proportions",
    "origami crane mascot that flies across the screen on startup",
]

class WeightedRandomSelector:
    """
    A class that tracks usage of items and decreases their probability of being selected.
    """
    def __init__(self, items, initial_weight=1.0, decay_factor=0.7):
        """
        Initialize the selector with items and their weights.
        
        Args:
            items: List of items to select from
            initial_weight: Starting weight for each item (default 1.0)
            decay_factor: Factor to multiply weight by after each use (default 0.7)
        """
        self.items = items
        self.weights = {item: initial_weight for item in items}
        self.decay_factor = decay_factor
        self.min_weight = 0.01  # Minimum weight to prevent items from being completely excluded
    
    def choose(self):
        """
        Choose an item based on current weights and update its weight.
        """
        # Get items and their current weights
        items_list = list(self.weights.keys())
        weights_list = list(self.weights.values())
        
        # Choose based on weights
        chosen = random.choices(items_list, weights=weights_list, k=1)[0]
        
        # Decrease weight of chosen item
        self.weights[chosen] = max(self.weights[chosen] * self.decay_factor, self.min_weight)
        
        return chosen
    
    def reset_weights(self, weight=1.0):
        """Reset all weights to a specific value."""
        for item in self.weights:
            self.weights[item] = weight

adj_selector = WeightedRandomSelector(adjectives, decay_factor=0.8)
noun_selector = WeightedRandomSelector(nouns, decay_factor=0.8)
verb_selector = WeightedRandomSelector(verbs, decay_factor=0.75)
qualifier_selector = WeightedRandomSelector(qualifiers, decay_factor=0.7)

ideas = []
for i in range(1000):
    if i == 6:
        ideas.append("Gay notebooks.") # Easter egg
        continue
    adj = adj_selector.choose()
    noun1 = noun_selector.choose()
    verb_phrase = verb_selector.choose()
    noun2 = noun_selector.choose()
    qualifier = qualifier_selector.choose()
    idea = f"A {adj} {noun1} that {verb_phrase} your {noun2}. {qualifier}"
    ideas.append(idea)

df = pd.DataFrame({"App Idea": ideas})

with open("prompts.txt", "w") as f:
    for idea in ideas:
        f.write(idea + "\n")