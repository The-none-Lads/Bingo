import pytest
from logic.modes import diagonals, four_corners, full_house, is_win, rows_completed


@pytest.fixture
def sample_grid():
    """Sample bingo grid for testing."""
    return [
        [1, 16, 31, 46, 61],
        [2, 17, 32, 47, 62],
        [3, 18, "FREE", 48, 63],
        [4, 19, 34, 49, 64],
        [5, 20, 35, 50, 65],
    ]


class TestRowsCompleted:
    """Test row completion logic."""

    def test_no_rows_completed(self, sample_grid):
        """Test when no rows are completed."""
        drawn = [1, 16]
        assert rows_completed(sample_grid, drawn) == 0

    def test_one_row_completed(self, sample_grid):
        """Test when one row is completed."""
        drawn = [1, 16, 31, 46, 61]
        assert rows_completed(sample_grid, drawn) == 1

    def test_multiple_rows_completed(self, sample_grid):
        """Test when multiple rows are completed."""
        drawn = [1, 16, 31, 46, 61, 2, 17, 32, 47, 62]  # Row 1  # Row 2
        assert rows_completed(sample_grid, drawn) == 2

    def test_row_with_free_space(self, sample_grid):
        """Test row completion with FREE space."""
        drawn = [3, 18, 48, 63]  # Row with FREE
        assert rows_completed(sample_grid, drawn) == 1

    def test_all_rows_completed(self, sample_grid):
        """Test when all rows are completed."""
        drawn = [
            1,
            16,
            31,
            46,
            61,
            2,
            17,
            32,
            47,
            62,
            3,
            18,
            48,
            63,
            4,
            19,
            34,
            49,
            64,
            5,
            20,
            35,
            50,
            65,
        ]
        assert rows_completed(sample_grid, drawn) == 5

    def test_partial_row(self, sample_grid):
        """Test partial row doesn't count as completed."""
        drawn = [1, 16, 31, 46]  # Missing one number
        assert rows_completed(sample_grid, drawn) == 0


class TestFourCorners:
    """Test four corners win condition."""

    def test_no_corners(self, sample_grid):
        """Test when no corners are marked."""
        drawn = []
        assert four_corners(sample_grid, drawn) is False

    def test_one_corner(self, sample_grid):
        """Test when only one corner is marked."""
        drawn = [1]  # Top-left
        assert four_corners(sample_grid, drawn) is False

    def test_three_corners(self, sample_grid):
        """Test when three corners are marked."""
        drawn = [1, 61, 5]  # Missing bottom-right
        assert four_corners(sample_grid, drawn) is False

    def test_all_four_corners(self, sample_grid):
        """Test when all four corners are marked."""
        drawn = [1, 61, 5, 65]
        assert four_corners(sample_grid, drawn) is True

    def test_four_corners_with_extra_numbers(self, sample_grid):
        """Test four corners with additional numbers drawn."""
        drawn = [1, 61, 5, 65, 10, 20, 30]
        assert four_corners(sample_grid, drawn) is True


class TestDiagonals:
    """Test diagonal win conditions."""

    def test_no_diagonal(self, sample_grid):
        """Test when no diagonal is complete."""
        drawn = [1, 2, 3]
        assert diagonals(sample_grid, drawn) is False

    def test_top_left_to_bottom_right(self, sample_grid):
        """Test main diagonal (top-left to bottom-right)."""
        drawn = [1, 17, 49, 65]  # FREE is at [2][2]
        assert diagonals(sample_grid, drawn) is True

    def test_top_right_to_bottom_left(self, sample_grid):
        """Test anti-diagonal (top-right to bottom-left)."""
        drawn = [61, 47, 19, 5]  # FREE is at [2][2]
        assert diagonals(sample_grid, drawn) is True

    def test_both_diagonals(self, sample_grid):
        """Test when both diagonals are complete."""
        drawn = [1, 17, 49, 65, 61, 47, 19, 5]
        assert diagonals(sample_grid, drawn) is True

    def test_partial_diagonal(self, sample_grid):
        """Test partial diagonal doesn't count."""
        drawn = [1, 17]  # Only 2 of 5 in diagonal
        assert diagonals(sample_grid, drawn) is False


class TestFullHouse:
    """Test full house (blackout) win condition."""

    def test_empty_card(self, sample_grid):
        """Test when card is empty."""
        drawn = []
        assert full_house(sample_grid, drawn) is False

    def test_partial_card(self, sample_grid):
        """Test when card is partially filled."""
        drawn = [1, 16, 31, 46, 61, 2, 17]
        assert full_house(sample_grid, drawn) is False

    def test_full_house_complete(self, sample_grid):
        """Test when all numbers are marked."""
        drawn = [
            1,
            16,
            31,
            46,
            61,
            2,
            17,
            32,
            47,
            62,
            3,
            18,
            48,
            63,
            4,
            19,
            34,
            49,
            64,
            5,
            20,
            35,
            50,
            65,
        ]
        assert full_house(sample_grid, drawn) is True

    def test_full_house_with_extra_numbers(self, sample_grid):
        """Test full house with extra numbers drawn."""
        drawn = list(range(1, 76))  # All possible numbers
        assert full_house(sample_grid, drawn) is True

    def test_full_house_missing_one(self, sample_grid):
        """Test that missing one number means no full house."""
        drawn = [
            1,
            16,
            31,
            46,
            61,
            2,
            17,
            32,
            47,
            62,
            3,
            18,
            48,
            63,
            4,
            19,
            34,
            49,
            64,
            5,
            20,
            35,
            50,
            # Missing 65
        ]
        assert full_house(sample_grid, drawn) is False


class TestIsWin:
    """Test the main is_win function with different modes."""

    def test_progressive_rows_win(self, sample_grid):
        """Test progressive rows win condition."""
        drawn = [1, 16, 31, 46, 61]  # One complete row
        valid, details = is_win("progressive_rows", 1, sample_grid, drawn)

        assert valid is True
        assert details["rows_completed"] == 1
        assert details["required_rows"] == 1

    def test_progressive_rows_not_enough(self, sample_grid):
        """Test progressive rows when not enough rows."""
        drawn = [1, 16, 31, 46, 61]  # One row
        valid, details = is_win("progressive_rows", 2, sample_grid, drawn)

        assert valid is False
        assert details["rows_completed"] == 1
        assert details["required_rows"] == 2

    def test_progressive_rows_exceed_requirement(self, sample_grid):
        """Test progressive rows when exceeding requirement."""
        drawn = [
            1,
            16,
            31,
            46,
            61,  # Row 1
            2,
            17,
            32,
            47,
            62,  # Row 2
            3,
            18,
            48,
            63,  # Row 3
        ]
        valid, details = is_win("progressive_rows", 2, sample_grid, drawn)

        assert valid is True
        assert details["rows_completed"] == 3

    def test_full_house_mode(self, sample_grid):
        """Test full house mode."""
        drawn = [
            1,
            16,
            31,
            46,
            61,
            2,
            17,
            32,
            47,
            62,
            3,
            18,
            48,
            63,
            4,
            19,
            34,
            49,
            64,
            5,
            20,
            35,
            50,
            65,
        ]
        valid, details = is_win("full_house", 1, sample_grid, drawn)

        assert valid is True
        assert details["required"] == "full_house"

    def test_four_corners_mode(self, sample_grid):
        """Test four corners mode."""
        drawn = [1, 61, 5, 65]
        valid, details = is_win("four_corners", 1, sample_grid, drawn)

        assert valid is True
        assert details["required"] == "four_corners"

    def test_diagonals_mode(self, sample_grid):
        """Test diagonals mode."""
        drawn = [1, 17, 49, 65]
        valid, details = is_win("diagonals", 1, sample_grid, drawn)

        assert valid is True
        assert details["required"] == "diagonals"

    def test_unknown_mode(self, sample_grid):
        """Test unknown mode returns False."""
        drawn = [1, 2, 3]
        valid, details = is_win("unknown_mode", 1, sample_grid, drawn)

        assert valid is False
        assert "required" in details


class TestEdgeCases:
    """Test edge cases for game modes."""

    def test_empty_grid(self):
        """Test with empty grid."""
        grid = [["FREE"] * 5 for _ in range(5)]
        drawn = list(range(1, 76))

        assert rows_completed(grid, drawn) == 5
        assert full_house(grid, drawn) is True

    def test_grid_with_all_numbers_drawn(self):
        """Test when all possible numbers are drawn."""
        grid = [[i + j * 5 + 1 for i in range(5)] for j in range(5)]
        grid[2][2] = "FREE"
        drawn = list(range(1, 76))

        assert full_house(grid, drawn) is True
        assert rows_completed(grid, drawn) == 5
        assert four_corners(grid, drawn) is True
        assert diagonals(grid, drawn) is True
