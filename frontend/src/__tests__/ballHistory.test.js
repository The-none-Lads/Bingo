import test from 'node:test';
import assert from 'node:assert/strict';
import { deriveBallState, getBallTransition } from '../ballHistory.js';

test('deriveBallState - handles empty and invalid inputs', () => {
  assert.deepEqual(deriveBallState([]), { current: null, history: [] });
  assert.deepEqual(deriveBallState(null), { current: null, history: [] });
  assert.deepEqual(deriveBallState(undefined), { current: null, history: [] });
});

test('deriveBallState - single draw', () => {
  const result = deriveBallState([42]);
  assert.equal(result.current, 42);
  assert.deepEqual(result.history, []);
});

test('deriveBallState - progression through 7 draws', () => {
  // Draw 1: [42]
  assert.deepEqual(deriveBallState([42]), { current: 42, history: [] });

  // Draw 2: [42, 17]
  assert.deepEqual(deriveBallState([42, 17]), { current: 17, history: [42] });

  // Draw 3: [42, 17, 8]
  assert.deepEqual(deriveBallState([42, 17, 8]), { current: 8, history: [17, 42] });

  // Draw 4: [42, 17, 8, 31]
  assert.deepEqual(deriveBallState([42, 17, 8, 31]), { current: 31, history: [8, 17, 42] });

  // Draw 5: [42, 17, 8, 31, 55]
  assert.deepEqual(deriveBallState([42, 17, 8, 31, 55]), { current: 55, history: [31, 8, 17, 42] });

  // Draw 6: [42, 17, 8, 31, 55, 73]
  assert.deepEqual(deriveBallState([42, 17, 8, 31, 55, 73]), {
    current: 73,
    history: [55, 31, 8, 17, 42],
  });

  // Draw 7: [42, 17, 8, 31, 55, 73, 9] -> 42 leaves history, max length 5
  assert.deepEqual(deriveBallState([42, 17, 8, 31, 55, 73, 9]), {
    current: 9,
    history: [73, 55, 31, 8, 17],
  });
  assert.equal(deriveBallState([42, 17, 8, 31, 55, 73, 9]).history.length, 5);
});

test('getBallTransition - handles hydration without animating past draws', () => {
  const transition = getBallTransition([], [10, 24, 51, 7, 42, 73]);
  assert.equal(transition.type, 'hydrate');
  assert.equal(transition.current, 73);
  assert.deepEqual(transition.history, [42, 7, 51, 24, 10]);
  assert.equal(transition.oldCurrent, null);
  assert.equal(transition.droppingBall, null);
});

test('getBallTransition - handles new draw transition metadata', () => {
  const prev = [42, 17, 8, 31, 55];
  const next = [42, 17, 8, 31, 55, 73];

  const transition = getBallTransition(prev, next);
  assert.equal(transition.type, 'draw');
  assert.equal(transition.current, 73);
  assert.equal(transition.oldCurrent, 55);
  assert.deepEqual(transition.history, [55, 31, 8, 17, 42]);
});

test('getBallTransition - detects dropping ball when history exceeds 5', () => {
  const prev = [42, 17, 8, 31, 55, 73];
  const next = [42, 17, 8, 31, 55, 73, 9];

  const transition = getBallTransition(prev, next);
  assert.equal(transition.type, 'draw');
  assert.equal(transition.current, 9);
  assert.equal(transition.oldCurrent, 73);
  assert.equal(transition.droppingBall, 42); // 42 was the 5th previous draw
  assert.deepEqual(transition.history, [73, 55, 31, 8, 17]);
});

test('getBallTransition - handles game reset', () => {
  const transition = getBallTransition([42, 17, 8], []);
  assert.equal(transition.type, 'reset');
  assert.equal(transition.current, null);
  assert.deepEqual(transition.history, []);
});
