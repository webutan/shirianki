from aqt.qt import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QScrollArea, QWidget, QProgressBar, QTimer
from aqt import mw
import random
import json
import os
from datetime import datetime

def normalize_kana(text):
    """Convert katakana to hiragana for comparison purposes"""
    if not text:
        return text

    result = []
    for char in text:
        code = ord(char)
        # Katakana range: 0x30A0-0x30FF
        # Hiragana range: 0x3040-0x309F
        # Offset between them is 0x60
        if 0x30A0 <= code <= 0x30FF:
            # Convert katakana to hiragana
            result.append(chr(code - 0x60))
        else:
            result.append(char)

    return ''.join(result)

def normalize_small_kana(char):
    """Convert small kana to their full-size equivalents"""
    # Mapping of small kana to full-size kana
    small_to_full = {
        # Hiragana
        'ゃ': 'や', 'ゅ': 'ゆ', 'ょ': 'よ',
        'ぁ': 'あ', 'ぃ': 'い', 'ぅ': 'う', 'ぇ': 'え', 'ぉ': 'お',
        'ゎ': 'わ', 'っ': 'つ',
        # Katakana
        'ャ': 'ヤ', 'ュ': 'ユ', 'ョ': 'ヨ',
        'ァ': 'ア', 'ィ': 'イ', 'ゥ': 'ウ', 'ェ': 'エ', 'ォ': 'オ',
        'ヮ': 'ワ', 'ッ': 'ツ', 'ヵ': 'カ', 'ヶ': 'ケ'
    }

    return small_to_full.get(char, char)

def count_scoring_kana(furigana):
    """Count kana for scoring, ignoring small kana and mora extension marks"""
    if not furigana:
        return 0

    # Small kana characters (ゃ ゅ ょ ぁ ぃ ぅ ぇ ぉ っ ゎ and katakana equivalents)
    small_kana = set([
        'ゃ', 'ゅ', 'ょ', 'ぁ', 'ぃ', 'ぅ', 'ぇ', 'ぉ', 'っ', 'ゎ',
        'ャ', 'ュ', 'ョ', 'ァ', 'ィ', 'ゥ', 'ェ', 'ォ', 'ッ', 'ヮ', 'ヵ', 'ヶ'
    ])

    count = 0
    for char in furigana:
        code = ord(char)
        # Check if it's a kana character (hiragana or katakana)
        is_kana = (0x3040 <= code <= 0x309F) or (0x30A0 <= code <= 0x30FF)

        # Count if it's kana and not a small kana or mora extension mark
        if is_kana and char not in small_kana and char != 'ー':
            count += 1

    return count

def calculate_score(kana_count):
    """Calculate score based on kana count"""
    if kana_count == 1:
        return 1
    elif kana_count == 2:
        return 3
    elif 3 <= kana_count <= 4:
        return 5
    elif 5 <= kana_count <= 6:
        return 10
    elif 7 <= kana_count <= 10:
        return 20
    else:  # > 10
        return 50

def get_praise_message(kana_count):
    """Get praise message based on kana count"""
    if 5 <= kana_count <= 6:
        return "ナイス！！"
    elif 7 <= kana_count <= 10:
        return "素晴らしい！！"
    elif kana_count > 10:
        return "天才じゃない？？"
    return ""

class ShiritoriGame(QDialog):
    def __init__(self, kanji_field, furigana_field, definition_field, example_field,
                 word_type_field, include_new_cards, word_basket_mode, nouns_only,
                 hint_mode, timer_seconds, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Shiritori Game" if not word_basket_mode else "ワードバスケット Game")
        self.setMinimumSize(800, 500)

        self.kanji_field = kanji_field
        self.furigana_field = furigana_field
        self.definition_field = definition_field
        self.example_field = example_field
        self.word_type_field = word_type_field
        self.include_new_cards = include_new_cards
        self.word_basket_mode = word_basket_mode
        self.nouns_only = nouns_only
        self.hint_mode = hint_mode
        self.timer_seconds = timer_seconds
        self.hint_shown = False  # Track if hint has been shown for current round

        # Load vocabulary from deck
        self.vocab = self.load_vocabulary()

        # Game state
        self.chain_count = 0
        self.total_score = 0  # Track total score
        self.last_word_kana_count = 0  # Track last word's kana count for praise message
        self.used_words = set()  # Track words that have been used (initialize early!)
        self.current_kana = self.get_random_starting_kana()
        self.required_ending_kana = ""  # For word basket mode
        if self.word_basket_mode:
            self.required_ending_kana = self.get_random_ending_kana(self.current_kana)
        self.previous_word_kanji = ""
        self.previous_word_furigana = ""
        self.previous_word_definition = ""
        self.previous_word_example = ""
        self.previous_word_is_new = False

        # Timer state
        self.time_remaining = timer_seconds
        self.timer = None

        # High scores file path
        addon_dir = os.path.dirname(__file__)
        self.high_scores_file = os.path.join(addon_dir, 'high_scores.json')

        # Setup UI
        self.setup_ui()
        self.update_display()

        # Start timer if enabled
        if self.timer_seconds > 0:
            self.start_timer()
    
    def setup_ui(self):
        # Main horizontal layout: left side (game) + right side (info)
        main_layout = QHBoxLayout()

        # Left side: Game area
        left_layout = QVBoxLayout()

        # Chain counter
        self.chain_label = QLabel()
        left_layout.addWidget(self.chain_label)

        # Current kana prompt (for word basket mode, show both starting and ending)
        self.kana_label = QLabel()
        self.kana_label.setStyleSheet("font-size: 48px; font-weight: bold;")
        left_layout.addWidget(self.kana_label)

        # Ending kana label (only visible in word basket mode)
        if self.word_basket_mode:
            self.ending_kana_label = QLabel()
            self.ending_kana_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #666;")
            left_layout.addWidget(self.ending_kana_label)

        # Previous word display
        self.prev_word_label = QLabel()
        self.prev_word_label.setStyleSheet("font-size: 24px;")
        left_layout.addWidget(self.prev_word_label)

        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a word...")
        self.input_field.returnPressed.connect(self.submit_word)
        left_layout.addWidget(self.input_field)

        # Error message
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        left_layout.addWidget(self.error_label)

        # Hint message (only shown when timer is low)
        self.hint_label = QLabel()
        self.hint_label.setStyleSheet("color: #FFA500; font-size: 14px; font-style: italic;")  # Orange color
        left_layout.addWidget(self.hint_label)

        # Buttons
        button_layout = QHBoxLayout()

        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self.submit_word)
        button_layout.addWidget(submit_btn)

        # Hint button (only show when timer is disabled and hint mode is enabled)
        if self.timer_seconds == 0 and self.hint_mode:
            self.hint_btn = QPushButton("Show Hint")
            self.hint_btn.clicked.connect(self.show_hint)
            button_layout.addWidget(self.hint_btn)

        end_btn = QPushButton("End Game")
        end_btn.clicked.connect(self.end_game)
        button_layout.addWidget(end_btn)

        left_layout.addLayout(button_layout)

        # Add stretch to push everything up
        left_layout.addStretch()

        # Right side: Definition and example
        right_layout = QVBoxLayout()

        # Definition label (no header, just content)
        self.definition_label = QLabel()
        self.definition_label.setWordWrap(True)
        self.definition_label.setStyleSheet("font-size: 24px;")
        right_layout.addWidget(self.definition_label)

        # Example sentence label (no header, just content)
        self.example_label = QLabel()
        self.example_label.setWordWrap(True)
        self.example_label.setStyleSheet("font-size: 24px;")
        right_layout.addWidget(self.example_label)

        # New word indicator (underneath example)
        self.new_word_label = QLabel()
        self.new_word_label.setStyleSheet("font-size: 12px; color: blue;")
        right_layout.addWidget(self.new_word_label)

        # Add stretch to push definition/example to top
        right_layout.addStretch()

        # Add both sides to main layout
        main_layout.addLayout(left_layout, 1)  # Left takes 1 part
        main_layout.addLayout(right_layout, 1)  # Right takes 1 part

        # Create overall layout with score and timer at bottom
        overall_layout = QVBoxLayout()
        overall_layout.addLayout(main_layout)

        # Score display with praise message
        score_layout = QHBoxLayout()
        self.score_label = QLabel("Score: 0")
        self.score_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        score_layout.addWidget(self.score_label)

        self.praise_label = QLabel()
        self.praise_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00FF00;")
        score_layout.addWidget(self.praise_label)

        score_layout.addStretch()
        overall_layout.addLayout(score_layout)

        # Timer progress bar at bottom (only if timer is enabled)
        if self.timer_seconds > 0:
            self.timer_bar = QProgressBar()
            self.timer_bar.setMaximum(self.timer_seconds * 10)  # 10 updates per second
            self.timer_bar.setValue(self.timer_seconds * 10)
            self.timer_bar.setTextVisible(False)
            overall_layout.addWidget(self.timer_bar)

        self.setLayout(overall_layout)

        # Focus on input
        self.input_field.setFocus()
    
    def load_vocabulary(self):
        """Load cards from current deck, optionally including new cards and filtering by word type"""
        vocab = {}  # {kanji: [{'furigana': str, 'definition': str, 'example': str, 'is_new': bool, 'word_type': str}, ...]}

        # Build query based on include_new_cards setting
        if self.include_new_cards:
            query = 'deck:current'
        else:
            query = 'deck:current -is:new'

        note_ids = mw.col.find_notes(query)

        for note_id in note_ids:
            note = mw.col.get_note(note_id)
            kanji = note[self.kanji_field].strip()
            furigana = note[self.furigana_field].strip()
            definition = note[self.definition_field].strip()
            example = note[self.example_field].strip()
            word_type = note[self.word_type_field].strip() if self.word_type_field else ""

            if kanji and furigana:
                # If nouns_only mode is enabled, filter out non-nouns
                if self.nouns_only and word_type:
                    # Case-insensitive check if "noun" appears anywhere in the word type
                    if "noun" not in word_type.lower():
                        continue  # Skip this word

                # Check if this card is new by looking at its cards
                is_new = False
                for card in note.cards():
                    if card.type == 0:  # 0 = new card
                        is_new = True
                        break

                reading_data = {
                    'furigana': furigana,
                    'definition': definition,
                    'example': example,
                    'is_new': is_new,
                    'word_type': word_type
                }

                # Store multiple readings per kanji
                if kanji in vocab:
                    vocab[kanji].append(reading_data)
                else:
                    vocab[kanji] = [reading_data]

        return vocab
    
    def get_first_kana(self, furigana):
        """Extract the first kana from furigana, ignoring non-kana characters, normalizing small kana"""
        if not furigana:
            return ""

        # Iterate forwards to find the first actual kana character
        for char in furigana:
            code = ord(char)

            # Check if character is hiragana (0x3040-0x309F) or katakana (0x30A0-0x30FF)
            if (0x3040 <= code <= 0x309F) or (0x30A0 <= code <= 0x30FF):
                # Normalize small kana to full-size (e.g., ょ -> よ)
                return normalize_small_kana(char)

        # If no kana found, return empty string
        return ""

    def get_random_starting_kana(self):
        """Pick a random kana that has available words"""
        if not self.vocab:
            return "あ"

        # Get all starting kana from vocabulary
        starting_kana = set()
        for readings in self.vocab.values():
            for reading_data in readings:
                furigana = reading_data['furigana']
                first_kana = self.get_first_kana(furigana)
                if first_kana:
                    starting_kana.add(first_kana)

        return random.choice(list(starting_kana)) if starting_kana else "あ"

    def get_last_kana(self, furigana):
        """Extract the last kana from furigana, ignoring non-kana characters and ー, normalizing small kana"""
        if not furigana:
            return ""

        # Iterate backwards to find the last actual kana character (excluding ー)
        for i in range(len(furigana) - 1, -1, -1):
            char = furigana[i]
            code = ord(char)

            # Check if character is hiragana (0x3040-0x309F) or katakana (0x30A0-0x30FF)
            # BUT skip ー (mora extension mark)
            if ((0x3040 <= code <= 0x309F) or (0x30A0 <= code <= 0x30FF)) and char != 'ー':
                # Normalize small kana to full-size (e.g., ょ -> よ)
                return normalize_small_kana(char)

        # If no kana found, return empty string
        return ""

    def get_random_ending_kana(self, starting_kana):
        """Pick a random ending kana that has at least one unused word matching both start AND end requirements"""
        if not self.vocab:
            return "あ"

        # Normalize starting kana for comparison
        normalized_starting = normalize_kana(starting_kana)

        # First, collect all possible ending kana from words that start with starting_kana
        candidate_ending_kana = set()
        for kanji, readings in self.vocab.items():
            # Skip words already used
            if kanji in self.used_words:
                continue

            for reading_data in readings:
                furigana = reading_data['furigana']
                first_kana = self.get_first_kana(furigana)
                normalized_first = normalize_kana(first_kana)

                # Check if this word starts with the required kana
                if normalized_first == normalized_starting:
                    # Get the ending kana and add to candidate set
                    last_kana = self.get_last_kana(furigana)
                    normalized_last = normalize_kana(last_kana)
                    # Don't use ん as ending kana (would end the game)
                    if normalized_last and normalized_last != "ん":
                        candidate_ending_kana.add(normalized_last)

        # Now verify each candidate ending kana has at least one word that satisfies BOTH requirements
        valid_ending_kana = set()
        for ending_kana in candidate_ending_kana:
            # Check if there exists at least one unused word that starts with starting_kana AND ends with ending_kana
            for kanji, readings in self.vocab.items():
                if kanji in self.used_words:
                    continue

                for reading_data in readings:
                    furigana = reading_data['furigana']
                    first_kana = self.get_first_kana(furigana)
                    normalized_first = normalize_kana(first_kana)
                    last_kana = self.get_last_kana(furigana)
                    normalized_last = normalize_kana(last_kana)

                    # Check if this word satisfies BOTH requirements
                    if normalized_first == normalized_starting and normalized_last == ending_kana:
                        valid_ending_kana.add(ending_kana)
                        break  # Found at least one word, this ending_kana is valid

                # If we found a valid reading, break outer loop too
                if ending_kana in valid_ending_kana:
                    break

        # If we found valid ending kana, pick one randomly
        if valid_ending_kana:
            return random.choice(list(valid_ending_kana))

        # Fallback: just pick any ending kana from vocabulary
        all_ending_kana = set()
        for readings in self.vocab.values():
            for reading_data in readings:
                last_kana = self.get_last_kana(reading_data['furigana'])
                normalized_last = normalize_kana(last_kana)
                if normalized_last and normalized_last != "ん":
                    all_ending_kana.add(normalized_last)

        return random.choice(list(all_ending_kana)) if all_ending_kana else "あ"

    def submit_word(self):
        input_word = self.input_field.text().strip()

        if not input_word:
            return

        # Check if word exists in vocabulary
        if input_word not in self.vocab:
            self.error_label.setText("Word not found in your deck!")
            return

        # Check if word has been used before
        if input_word in self.used_words:
            self.error_label.setText("Word already used!")
            self.end_game()
            return

        # Get all readings for this kanji
        readings = self.vocab[input_word]

        # Find a reading that matches the current requirements
        valid_reading = None
        for reading_data in readings:
            furigana = reading_data['furigana']

            # Check if starts with correct kana (normalize both for comparison)
            first_kana = self.get_first_kana(furigana)
            normalized_first = normalize_kana(first_kana)
            normalized_current = normalize_kana(self.current_kana)

            if normalized_first != normalized_current:
                continue  # This reading doesn't match starting kana

            # Get last kana for validation
            last_kana = self.get_last_kana(furigana)
            normalized_last_kana = normalize_kana(last_kana)

            # In word basket mode, also check if ends with required ending kana
            if self.word_basket_mode:
                normalized_required_ending = normalize_kana(self.required_ending_kana)
                if normalized_last_kana != normalized_required_ending:
                    continue  # This reading doesn't match ending kana

            # Check if ends with ん (normalize to catch both ん and ン)
            if normalized_last_kana == "ん":
                self.error_label.setText("Game over! Word ended with ん")
                self.end_game()
                return

            # Found a valid reading!
            valid_reading = reading_data
            break

        # If no valid reading found
        if not valid_reading:
            if self.word_basket_mode:
                self.error_label.setText(f"Must start with {self.current_kana} and end with {self.required_ending_kana}!")
            else:
                self.error_label.setText(f"Must start with {self.current_kana}!")
            return

        # Use the valid reading
        furigana = valid_reading['furigana']
        definition = valid_reading['definition']
        example = valid_reading['example']
        is_new = valid_reading['is_new']

        # Get last kana from the valid reading
        last_kana = self.get_last_kana(furigana)

        # Valid word!
        self.chain_count += 1
        self.used_words.add(input_word)  # Track this word as used

        # Calculate score for this word
        kana_count = count_scoring_kana(furigana)
        points = calculate_score(kana_count)
        self.total_score += points
        self.last_word_kana_count = kana_count

        self.previous_word_kanji = input_word
        self.previous_word_furigana = furigana
        self.previous_word_definition = definition
        self.previous_word_example = example
        self.previous_word_is_new = is_new
        # Normalize the next required kana to ensure consistency
        self.current_kana = normalize_kana(last_kana)

        # In word basket mode, pick a new random ending kana
        if self.word_basket_mode:
            self.required_ending_kana = self.get_random_ending_kana(self.current_kana)

        # Reset timer if enabled
        if self.timer_seconds > 0:
            self.time_remaining = self.timer_seconds
            self.timer_bar.setValue(self.timer_seconds * 10)

        # Clear input, error, and hint
        self.input_field.clear()
        self.error_label.clear()
        self.clear_hint()

        self.update_display()
    
    def update_display(self):
        # Update chain counter
        self.chain_label.setText(f"Chain: {self.chain_count} words")

        # Update current kana
        if self.word_basket_mode:
            self.kana_label.setText(f"Start: {self.current_kana}")
            self.ending_kana_label.setText(f"End: {self.required_ending_kana}")
        else:
            self.kana_label.setText(self.current_kana)

        # Update previous word
        if self.previous_word_kanji:
            # Highlight last kana (simple version - just show it separately)
            display_text = f"{self.previous_word_kanji}\n{self.previous_word_furigana}"
            self.prev_word_label.setText(display_text)
        else:
            self.prev_word_label.setText("Start your chain!")

        # Update definition and example
        if self.previous_word_definition:
            self.definition_label.setText(self.previous_word_definition)
        else:
            self.definition_label.setText("No definition available")

        if self.previous_word_example:
            self.example_label.setText(self.previous_word_example)
        else:
            self.example_label.setText("No example available")

        # Update new word indicator
        if self.previous_word_is_new:
            self.new_word_label.setText("New word!")
        else:
            self.new_word_label.setText("")

        # Update score display
        self.score_label.setText(f"Score: {self.total_score}")

        # Update praise message
        praise = get_praise_message(self.last_word_kana_count)
        self.praise_label.setText(praise)
    
    def start_timer(self):
        """Start the countdown timer"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(100)  # Update every 100ms (10 times per second)

    def update_timer(self):
        """Update the timer countdown"""
        if self.time_remaining > 0:
            # Decrease by 0.1 seconds
            self.time_remaining -= 0.1
            # Update progress bar (multiply by 10 for precision)
            self.timer_bar.setValue(int(self.time_remaining * 10))

            # Show hint when timer is below 25% (if hint mode enabled and not already shown)
            if self.hint_mode and not self.hint_shown:
                time_percentage = (self.time_remaining / self.timer_seconds) * 100
                if time_percentage < 25:
                    self.show_hint()
                    self.hint_shown = True
        else:
            # Time's up!
            self.timer.stop()
            self.error_label.setText("Time's up!")
            self.end_game()

    def show_hint(self):
        """Display a hint word that matches the current requirements"""
        example = self.find_valid_word_example()
        if example:
            hint_text = f" Hint: {example['kanji']}"
            if self.word_basket_mode:
                hint_text += f" (starts: {self.current_kana}, ends: {self.required_ending_kana})"
            else:
                hint_text += f" (starts: {self.current_kana})"
            self.hint_label.setText(hint_text)
        else:
            self.hint_label.setText("Hint: No valid words found!")

    def clear_hint(self):
        """Clear the hint display"""
        self.hint_label.setText("")
        self.hint_shown = False

    def find_valid_word_example(self):
        """Find an unused word that matches the current requirements"""
        normalized_current = normalize_kana(self.current_kana)

        # Build list of valid words
        valid_words = []
        for kanji, readings in self.vocab.items():
            # Skip words already used
            if kanji in self.used_words:
                continue

            for reading_data in readings:
                furigana = reading_data['furigana']
                first_kana = self.get_first_kana(furigana)
                normalized_first = normalize_kana(first_kana)

                # Check if starts with required kana
                if normalized_first != normalized_current:
                    continue

                # In word basket mode, also check ending kana
                if self.word_basket_mode:
                    last_kana = self.get_last_kana(furigana)
                    normalized_last = normalize_kana(last_kana)
                    normalized_required_ending = normalize_kana(self.required_ending_kana)

                    if normalized_last != normalized_required_ending:
                        continue

                # Check it doesn't end with ん
                last_kana = self.get_last_kana(furigana)
                normalized_last = normalize_kana(last_kana)
                if normalized_last == "ん":
                    continue

                # This is a valid word!
                valid_words.append({
                    'kanji': kanji,
                    'furigana': furigana,
                    'definition': reading_data['definition']
                })
                break  # Only add one reading per kanji to avoid duplicates

        # Return a random valid word if any exist
        if valid_words:
            return random.choice(valid_words)
        return None

    def load_high_scores(self):
        """Load high scores from file"""
        if not os.path.exists(self.high_scores_file):
            return {'normal': [], 'word_basket': []}

        try:
            with open(self.high_scores_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {'normal': [], 'word_basket': []}

    def save_high_scores(self, high_scores):
        """Save high scores to file"""
        try:
            with open(self.high_scores_file, 'w', encoding='utf-8') as f:
                json.dump(high_scores, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving high scores: {e}")

    def add_high_score(self, score, mode):
        """Add a new high score and keep top 10"""
        high_scores = self.load_high_scores()

        # Get the appropriate mode list
        mode_key = 'word_basket' if mode else 'normal'
        scores_list = high_scores.get(mode_key, [])

        # Add new score with timestamp
        new_entry = {
            'score': score,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'chain': self.chain_count
        }
        scores_list.append(new_entry)

        # Sort by score (descending) and keep top 10
        scores_list.sort(key=lambda x: x['score'], reverse=True)
        scores_list = scores_list[:10]

        # Update high scores
        high_scores[mode_key] = scores_list
        self.save_high_scores(high_scores)

        return scores_list

    def format_high_scores(self, scores_list):
        """Format high scores list for display"""
        if not scores_list:
            return "No scores yet!"

        result = []
        for i, entry in enumerate(scores_list, 1):
            result.append(f"{i}. {entry['score']} pts (Chain: {entry['chain']}) - {entry['date']}")

        return "\n".join(result)

    def end_game(self):
        # Stop timer if running
        if self.timer:
            self.timer.stop()

        from aqt.utils import showInfo

        # Build game over message
        mode_name = "ワードバスケット" if self.word_basket_mode else "Normal"
        message = f"Game Over!\nMode: {mode_name}\nFinal chain: {self.chain_count} words\nFinal score: {self.total_score} points"

        # Add hint mode indicator if used
        if self.hint_mode:
            message += "\n(Hint mode enabled - score not saved)"

        # In word basket mode, show an example word if available
        if self.word_basket_mode:
            example = self.find_valid_word_example()
            if example:
                message += f"\n\nExample word:\n{example['kanji']} ({example['furigana']})"
                if example['definition']:
                    message += f"\n{example['definition']}"

        # Only save and display high scores if hint mode is NOT enabled
        if not self.hint_mode:
            # Save high score
            scores_list = self.add_high_score(self.total_score, self.word_basket_mode)

            # Add high scores
            message += f"\n\n=== Top 10 High Scores ({mode_name}) ===\n"
            message += self.format_high_scores(scores_list)

        showInfo(message)
        self.close()
