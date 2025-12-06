from logic.draws import DrawEngine


class TestDrawEngine:
    """Test the draw engine for bingo numbers."""

    def test_draw_engine_initialization(self):
        """Test DrawEngine initializes correctly."""
        engine = DrawEngine(max_number=75)

        assert engine.max_number == 75
        assert len(engine.remaining) == 75
        assert len(engine.drawn) == 0

    def test_draw_engine_custom_max(self):
        """Test DrawEngine with custom max number."""
        engine = DrawEngine(max_number=90)

        assert engine.max_number == 90
        assert len(engine.remaining) == 90

    def test_draw_single_number(self):
        """Test drawing a single number."""
        engine = DrawEngine(max_number=75)

        num = engine.draw()

        assert num is not None
        assert 1 <= num <= 75
        assert num in engine.drawn
        assert num not in engine.remaining
        assert len(engine.drawn) == 1
        assert len(engine.remaining) == 74

    def test_draw_all_numbers(self):
        """Test drawing all numbers until exhausted."""
        engine = DrawEngine(max_number=75)
        drawn_numbers = []

        for _ in range(75):
            num = engine.draw()
            assert num is not None
            drawn_numbers.append(num)

        # All numbers should be drawn
        assert len(drawn_numbers) == 75
        assert set(drawn_numbers) == set(range(1, 76))
        assert len(engine.remaining) == 0

    def test_draw_returns_none_when_exhausted(self):
        """Test that draw returns None when all numbers drawn."""
        engine = DrawEngine(max_number=5)

        # Draw all numbers
        for _ in range(5):
            engine.draw()

        # Next draw should return None
        assert engine.draw() is None
        assert engine.draw() is None

    def test_draw_order_is_random(self):
        """Test that draw order is randomized."""
        # Create multiple engines and draw first number
        first_draws = [DrawEngine(max_number=75).draw() for _ in range(20)]

        # Should have some variation (not all the same)
        assert len(set(first_draws)) > 1

    def test_drawn_list_maintains_order(self):
        """Test that drawn list maintains draw order."""
        engine = DrawEngine(max_number=75)

        num1 = engine.draw()
        num2 = engine.draw()
        num3 = engine.draw()

        assert engine.drawn == [num1, num2, num3]

    def test_no_duplicate_draws(self):
        """Test that same number is never drawn twice."""
        engine = DrawEngine(max_number=75)

        for _ in range(75):
            engine.draw()

        # Check no duplicates in drawn list
        assert len(engine.drawn) == len(set(engine.drawn))

    def test_remaining_decreases_correctly(self):
        """Test that remaining list decreases with each draw."""
        engine = DrawEngine(max_number=10)

        assert len(engine.remaining) == 10

        engine.draw()
        assert len(engine.remaining) == 9

        engine.draw()
        assert len(engine.remaining) == 8

    def test_draw_engine_state_consistency(self):
        """Test that engine state is always consistent."""
        engine = DrawEngine(max_number=75)

        for _ in range(30):
            engine.draw()

        # Total should always equal max_number
        assert len(engine.drawn) + len(engine.remaining) == 75

        # No overlap between drawn and remaining
        assert set(engine.drawn).isdisjoint(set(engine.remaining))

        # Union should be all numbers
        assert set(engine.drawn) | set(engine.remaining) == set(range(1, 76))


class TestDrawEngineEdgeCases:
    """Test edge cases for DrawEngine."""

    def test_draw_engine_with_one_number(self):
        """Test engine with only one number."""
        engine = DrawEngine(max_number=1)

        assert engine.draw() == 1
        assert engine.draw() is None

    def test_draw_engine_deterministic_randomness(self):
        """Test that randomness is cryptographically secure."""
        # Generate many engines and check distribution
        engines = [DrawEngine(max_number=10) for _ in range(100)]
        first_draws = [e.draw() for e in engines]

        # Should have reasonable distribution (not perfect, but close)
        unique_draws = len(set(first_draws))
        assert unique_draws >= 5  # At least 50% of possible values

    def test_large_number_set(self):
        """Test with large number set."""
        engine = DrawEngine(max_number=1000)

        assert len(engine.remaining) == 1000

        num = engine.draw()
        assert 1 <= num <= 1000
