import pytest
from logic.cards import (
    generate_75_ball_card,
    serialize_card,
    deserialize_card,
    short_id
)


class TestCardGeneration:
    """Test bingo card generation logic."""
    
    def test_generate_75_ball_card_structure(self):
        """Test that generated card has correct structure."""
        card = generate_75_ball_card()
        
        # Should be 5x5 grid
        assert len(card) == 5
        assert all(len(row) == 5 for row in card)
    
    def test_generate_75_ball_card_free_space(self):
        """Test that center space is FREE."""
        card = generate_75_ball_card()
        assert card[2][2] == "FREE"
    
    def test_generate_75_ball_card_column_ranges(self):
        """Test that numbers are in correct column ranges."""
        card = generate_75_ball_card()
        
        # Transpose to get columns
        columns = [[card[row][col] for row in range(5)] for col in range(5)]
        
        # B column: 1-15
        for val in columns[0]:
            if val != "FREE":
                assert 1 <= val <= 15
        
        # I column: 16-30
        for val in columns[1]:
            if val != "FREE":
                assert 16 <= val <= 30
        
        # N column: 31-45 (has FREE in middle)
        for i, val in enumerate(columns[2]):
            if val != "FREE":
                assert 31 <= val <= 45
        
        # G column: 46-60
        for val in columns[3]:
            if val != "FREE":
                assert 46 <= val <= 60
        
        # O column: 61-75
        for val in columns[4]:
            if val != "FREE":
                assert 61 <= val <= 75
    
    def test_generate_75_ball_card_no_duplicates(self):
        """Test that card has no duplicate numbers."""
        card = generate_75_ball_card()
        numbers = [cell for row in card for cell in row if cell != "FREE"]
        assert len(numbers) == len(set(numbers))
    
    def test_generate_multiple_unique_cards(self):
        """Test that multiple generated cards are different."""
        cards = [generate_75_ball_card() for _ in range(10)]
        serialized = [serialize_card(card) for card in cards]
        
        # All cards should be unique
        assert len(set(serialized)) == 10


class TestCardSerialization:
    """Test card serialization and deserialization."""
    
    def test_serialize_card(self):
        """Test serializing a card to string."""
        card = [[1, 2, 3, 4, 5] for _ in range(5)]
        card[2][2] = "FREE"
        
        serialized = serialize_card(card)
        
        assert isinstance(serialized, str)
        assert "FREE" in serialized
        assert ";" in serialized  # Row separator
        assert "," in serialized  # Column separator
    
    def test_deserialize_card(self):
        """Test deserializing a card from string."""
        serialized = "1,2,3,4,5;6,7,8,9,10;11,12,FREE,14,15;16,17,18,19,20;21,22,23,24,25"
        card = deserialize_card(serialized)
        
        assert len(card) == 5
        assert len(card[0]) == 5
        assert card[2][2] == "FREE"
        assert card[0][0] == 1
        assert card[4][4] == 25
    
    def test_serialize_deserialize_roundtrip(self):
        """Test that serialize->deserialize returns original card."""
        original = generate_75_ball_card()
        serialized = serialize_card(original)
        deserialized = deserialize_card(serialized)
        
        assert original == deserialized
    
    def test_short_id_generation(self):
        """Test generating short IDs from serialized cards."""
        card = generate_75_ball_card()
        serial = serialize_card(card)
        short = short_id(serial)
        
        assert isinstance(short, str)
        assert len(short) == 8
        assert short.isupper()
        assert short.isalnum()
    
    def test_short_id_deterministic(self):
        """Test that same card always generates same ID."""
        card = generate_75_ball_card()
        serial = serialize_card(card)
        
        id1 = short_id(serial)
        id2 = short_id(serial)
        
        assert id1 == id2
    
    def test_short_id_unique(self):
        """Test that different cards generate different IDs."""
        cards = [generate_75_ball_card() for _ in range(100)]
        ids = [short_id(serialize_card(card)) for card in cards]
        
        # Should have high uniqueness (allow for very rare collisions)
        assert len(set(ids)) >= 99


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_deserialize_invalid_format(self):
        """Test deserializing invalid format raises error."""
        with pytest.raises(Exception):
            deserialize_card("invalid")
    
    def test_short_id_custom_length(self):
        """Test custom length for short IDs."""
        serial = serialize_card(generate_75_ball_card())
        
        short_4 = short_id(serial, length=4)
        short_16 = short_id(serial, length=16)
        
        assert len(short_4) == 4
        assert len(short_16) == 16
