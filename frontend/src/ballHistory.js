/**
 * ballHistory.js - Pure functions for managing authoritative Bingo ball state and history transitions.
 */

/**
 * Derives the current main ball and the 5-ball recent history from an authoritative drawn array.
 *
 * Rules:
 * - current: The newest draw (last element in drawn array) or null if drawn is empty.
 * - history: Up to 5 previous draws in reverse order (most recent first).
 * - The current ball is NEVER in history.
 *
 * @param {number[]} drawn - Authoritative list of drawn numbers in chronological order.
 * @returns {{ current: number | null, history: number[] }}
 */
export function deriveBallState(drawn) {
  if (!Array.isArray(drawn) || drawn.length === 0) {
    return { current: null, history: [] };
  }
  const current = drawn[drawn.length - 1];
  const previousDraws = drawn.slice(0, -1);
  const history = previousDraws.slice(-5).reverse();
  return { current, history };
}

/**
 * Calculates transition metadata when comparing a previous drawn list to a new drawn list.
 *
 * @param {number[]} prevDrawn - Previous drawn list
 * @param {number[]} newDrawn - Newly received drawn list
 * @returns {{
 *   type: 'reset' | 'hydrate' | 'draw' | 'noop',
 *   current: number | null,
 *   history: number[],
 *   oldCurrent: number | null,
 *   droppingBall: number | null
 * }}
 */
export function getBallTransition(prevDrawn = [], newDrawn = []) {
  const prevList = Array.isArray(prevDrawn) ? prevDrawn : [];
  const newList = Array.isArray(newDrawn) ? newDrawn : [];

  if (newList.length === 0) {
    return {
      type: 'reset',
      current: null,
      history: [],
      oldCurrent: null,
      droppingBall: null,
    };
  }

  // Initial load / hydration
  if (prevList.length === 0 && newList.length > 0) {
    const { current, history } = deriveBallState(newList);
    return {
      type: 'hydrate',
      current,
      history,
      oldCurrent: null,
      droppingBall: null,
    };
  }

  // A new draw arrived
  if (newList.length > prevList.length) {
    const oldCurrent = prevList[prevList.length - 1];
    const newCurrent = newList[newList.length - 1];
    const { history: targetHistory } = deriveBallState(newList);

    // Oldest history item that gets pushed out if history was already at capacity (5)
    const prevHistory = prevList.slice(0, -1).slice(-5).reverse();
    const droppingBall = prevHistory.length >= 5 ? prevHistory[4] : null;

    return {
      type: 'draw',
      current: newCurrent,
      history: targetHistory,
      oldCurrent,
      droppingBall,
    };
  }

  // Same state / no new draws
  const { current, history } = deriveBallState(newList);
  return {
    type: 'noop',
    current,
    history,
    oldCurrent: null,
    droppingBall: null,
  };
}
