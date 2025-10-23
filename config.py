from aqt.qt import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QCheckBox, QLineEdit, QHBoxLayout
from aqt import mw

# Get the addon package name for config access
ADDON_PACKAGE = __name__.split('.')[0]

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Shiritori Configuration")
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        # Get current deck and its note type
        deck_name = mw.col.decks.current()['name']
        layout.addWidget(QLabel(f"Current deck: {deck_name}"))

        # Kanji field selector
        layout.addWidget(QLabel("Kanji field:"))
        self.kanji_combo = QComboBox()
        layout.addWidget(self.kanji_combo)

        # Furigana field selector
        layout.addWidget(QLabel("Furigana field:"))
        self.furigana_combo = QComboBox()
        layout.addWidget(self.furigana_combo)

        # Definition field selector
        layout.addWidget(QLabel("Definition field:"))
        self.definition_combo = QComboBox()
        layout.addWidget(self.definition_combo)

        # Example sentence field selector
        layout.addWidget(QLabel("Example sentence field:"))
        self.example_combo = QComboBox()
        layout.addWidget(self.example_combo)

        # Word type field selector
        layout.addWidget(QLabel("Word type field (for nouns only mode):"))
        self.word_type_combo = QComboBox()
        layout.addWidget(self.word_type_combo)

        # Include new cards checkbox
        self.include_new_checkbox = QCheckBox("Include new cards")
        self.include_new_checkbox.setChecked(False)  # Default to not including new cards
        layout.addWidget(self.include_new_checkbox)

        # Word Basket mode checkbox
        self.word_basket_checkbox = QCheckBox("ワードバスケット mode (must match starting AND ending kana)")
        self.word_basket_checkbox.setChecked(False)  # Default to regular shiritori
        layout.addWidget(self.word_basket_checkbox)

        # Nouns only checkbox
        self.nouns_only_checkbox = QCheckBox("Nouns only (only accept/consider words marked as noun)")
        self.nouns_only_checkbox.setChecked(True)  # Default to nouns only
        layout.addWidget(self.nouns_only_checkbox)

        # Timer option
        timer_layout = QHBoxLayout()
        timer_layout.addWidget(QLabel("Timer (seconds, 0 = no timer):"))
        self.timer_input = QLineEdit()
        self.timer_input.setPlaceholderText("0")
        self.timer_input.setMaximumWidth(100)
        timer_layout.addWidget(self.timer_input)
        timer_layout.addStretch()
        layout.addLayout(timer_layout)

        # Hint mode checkbox
        self.hint_mode_checkbox = QCheckBox("Enable hints (shows a valid word when timer <25%)")
        self.hint_mode_checkbox.setChecked(False)  # Default to no hints
        layout.addWidget(self.hint_mode_checkbox)

        # Populate dropdowns with available fields
        self.populate_fields()

        # Load saved selections
        self.load_saved_config()

        # Start button
        self.start_btn = QPushButton("Start Game")
        self.start_btn.clicked.connect(self.start_game)
        layout.addWidget(self.start_btn)

        self.setLayout(layout)
    
    def populate_fields(self):
        """Get field names from the current deck's note types"""
        # Get all note types used in current deck
        deck_id = mw.col.decks.current()['id']
        note_ids = mw.col.find_notes(f'deck:current')

        if note_ids:
            # Get first note to extract field names
            note = mw.col.get_note(note_ids[0])
            field_names = note.keys()

            self.kanji_combo.addItems(field_names)
            self.furigana_combo.addItems(field_names)
            self.definition_combo.addItems(field_names)
            self.example_combo.addItems(field_names)
            self.word_type_combo.addItems(field_names)

    def load_saved_config(self):
        """Load previously saved field selections"""
        config = mw.addonManager.getConfig(ADDON_PACKAGE)
        if config:
            kanji_field = config.get('kanji_field')
            furigana_field = config.get('furigana_field')
            definition_field = config.get('definition_field')
            example_field = config.get('example_field')
            word_type_field = config.get('word_type_field')
            include_new = config.get('include_new_cards', False)
            word_basket_mode = config.get('word_basket_mode', False)
            nouns_only = config.get('nouns_only', True)
            timer_seconds = config.get('timer_seconds', 0)
            hint_mode = config.get('hint_mode', False)

            # Set combo boxes to saved values if they exist
            if kanji_field:
                index = self.kanji_combo.findText(kanji_field)
                if index >= 0:
                    self.kanji_combo.setCurrentIndex(index)

            if furigana_field:
                index = self.furigana_combo.findText(furigana_field)
                if index >= 0:
                    self.furigana_combo.setCurrentIndex(index)

            if definition_field:
                index = self.definition_combo.findText(definition_field)
                if index >= 0:
                    self.definition_combo.setCurrentIndex(index)

            if example_field:
                index = self.example_combo.findText(example_field)
                if index >= 0:
                    self.example_combo.setCurrentIndex(index)

            if word_type_field:
                index = self.word_type_combo.findText(word_type_field)
                if index >= 0:
                    self.word_type_combo.setCurrentIndex(index)

            # Set checkbox and timer values
            self.include_new_checkbox.setChecked(include_new)
            self.word_basket_checkbox.setChecked(word_basket_mode)
            self.nouns_only_checkbox.setChecked(nouns_only)
            self.hint_mode_checkbox.setChecked(hint_mode)
            self.timer_input.setText(str(timer_seconds))

    def save_config(self):
        """Save current field selections"""
        # Parse timer input, default to 0 if invalid
        try:
            timer_seconds = int(self.timer_input.text() or "0")
        except ValueError:
            timer_seconds = 0

        config = {
            'kanji_field': self.kanji_combo.currentText(),
            'furigana_field': self.furigana_combo.currentText(),
            'definition_field': self.definition_combo.currentText(),
            'example_field': self.example_combo.currentText(),
            'word_type_field': self.word_type_combo.currentText(),
            'include_new_cards': self.include_new_checkbox.isChecked(),
            'word_basket_mode': self.word_basket_checkbox.isChecked(),
            'nouns_only': self.nouns_only_checkbox.isChecked(),
            'hint_mode': self.hint_mode_checkbox.isChecked(),
            'timer_seconds': timer_seconds
        }
        mw.addonManager.writeConfig(ADDON_PACKAGE, config)

    def start_game(self):
        kanji_field = self.kanji_combo.currentText()
        furigana_field = self.furigana_combo.currentText()
        definition_field = self.definition_combo.currentText()
        example_field = self.example_combo.currentText()
        word_type_field = self.word_type_combo.currentText()
        include_new_cards = self.include_new_checkbox.isChecked()
        word_basket_mode = self.word_basket_checkbox.isChecked()
        nouns_only = self.nouns_only_checkbox.isChecked()
        hint_mode = self.hint_mode_checkbox.isChecked()

        # Parse timer input
        try:
            timer_seconds = int(self.timer_input.text() or "0")
        except ValueError:
            timer_seconds = 0

        # Save the configuration
        self.save_config()

        from .game_window import ShiritoriGame

        self.close()

        game = ShiritoriGame(kanji_field, furigana_field, definition_field, example_field,
                            word_type_field, include_new_cards, word_basket_mode, nouns_only,
                            hint_mode, timer_seconds, mw)
        game.exec()
        
