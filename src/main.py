#!/usr/bin/env python
#
# Sample dropblox_ai exectuable.
#

import json
import sys
import time

class InvalidMoveError(ValueError):
  pass

# A class representing an (i, j) position on a board.
class Point(object):
  def __init__(self, i=0, j=0):
    self.i = i
    self.j = j

# A class representing a Block object.
class Block(object):
  def __init__(self, center, offsets):
    # The block's center and offsets should not be mutated.
    self.center = Point(center['i'], center['j'])
    self.offsets = tuple(Point(offset['i'], offset['j']) for offset in offsets)
    # To move the block, we can change the Point "translation" or increment
    # the value "rotation".
    self.translation = Point()
    self.rotation = 0

  # A generator that returns a list of squares currently occupied by this
  # block. Takes translations and rotations into account.
  def squares(self):
    if self.rotation % 2:
      for offset in self.offsets:
        yield Point(
          self.center.i + self.translation.i + (2 - self.rotation)*offset.j,
          self.center.j + self.translation.j - (2 - self.rotation)*offset.i,
        )
    else:
      for offset in self.offsets:
        yield Point(
          self.center.i + self.translation.i + (1 - self.rotation)*offset.i,
          self.center.j + self.translation.j + (1 - self.rotation)*offset.j,
        )

  def left(self):
    self.translation.j -= 1

  def right(self):
    self.translation.j += 1

  def up(self):
    self.translation.i -= 1

  def down(self):
    self.translation.i += 1

  def rotate(self):
    self.rotation += 1

  def unrotate(self):
    self.rotation -= 1

  # The checked_* methods below perform an operation on the block
  # only if it's a legal move on the passed in board.  They
  # return True if the move succeeded.
  def checked_left(self, board):
    self.left()
    if board.check(self):
        return True
    self.right()
    return False

  def checked_right(self, board):
    self.right()
    if board.check(self):
        return True
    self.left()
    return False

  def checked_down(self, board):
    self.down()
    if board.check(self):
        return True
    self.up()
    return False

  def checked_up(self, board):
    self.up()
    if board.check(self):
        return True
    self.down()
    return False

  def checked_rotate(self, board):
    self.rotate()
    if board.check(self):
        return True
    self.unrotate()
    return False

  def do_command(self, command):
    assert(command in ('left', 'right', 'up', 'down', 'rotate')), \
        'Unexpected command %s' % (command,)
    getattr(self, command)()

  def do_commands(self, commands):
    for command in commands:
      self.do_command(command)

  def reset_position(self):
    (self.translation.i, self.translation.j) = (0, 0)
    self.rotation = 0

# A class representing a board state. Stores the current block and the
# preview list and handles commands.
class Board(object):
  rows = 33
  cols = 12

  def __init__(self, bitmap, block, preview):
    self.bitmap = bitmap
    self.block = block
    self.preview = preview

  def __repr__(self):
    return str(self)

  def __str__(self):
    return '\n'.join(' '.join('X' if elt else '.' for elt in row) for row in self.bitmap)

  @staticmethod
  def construct_from_json(state_json):
    state = json.loads(state_json)
    block = Block(state['block']['center'], state['block']['offsets'])
    preview = [Block(data['center'], data['offsets']) for data in state['preview']]
    return Board(state['bitmap'], block, preview)

  # Returns True if the block is in valid position - that is, if all of its squares
  # are in bounds and are currently unoccupied.
  def check(self, block):
    for square in block.squares():
      if (square.i < 0 or square.i >= self.rows or
          square.j < 0 or square.j >= self.cols or
          self.bitmap[square.i][square.j]):
        return False
    return True

  # Handles a list of commands to move the current block, and drops it at the end.
  # Appends a 'drop' command to the list if it does not appear, and returns the
  # new Board state object.
  #
  # If the block is ever in an invalid position during this method, throws an
  # InvalidMoveError.
  def do_commands(self, commands):
    self.block.reset_position()
    if not self.check(self.block):
      raise InvalidMoveError()
    commands.append('drop')
    for command in commands:
      if command == 'drop':
        new_board = self.place()
        return new_board
      else:
        self.block.do_command(command)
        if not self.check(self.block):
          raise InvalidMoveError()

  # Drops the current block as far as it can fall unobstructed, then locks it onto the
  # board. Returns a new board with the next block drawn from the preview list.
  #
  # Assumes the block starts out in valid position. This method mutates the current block
  #
  # If there are no blocks left in the preview list, this method will fail badly!
  # This is okay because we don't expect to look ahead that far.
  def place(self):
    while self.check(self.block):
      self.block.down()
    self.block.up()
    # Deep-copy the bitmap to avoid changing this board's state.
    new_bitmap = [list(row) for row in self.bitmap]
    for square in self.block.squares():
      new_bitmap[square.i][square.j] = 1
    new_bitmap = Board.remove_rows(new_bitmap)
    if len(self.preview) == 0:
      print "There are no blocks left in the preview list! You can't look that far ahead."
      return None
    return Board(new_bitmap, self.preview[0], self.preview[1:])

  # A helper method used to remove any full rows from a bitmap. Returns the new bitmap.
  @staticmethod
  def remove_rows(bitmap):
    (rows, cols) = (len(bitmap), len(bitmap[0]))
    new_bitmap = [row for row in bitmap if not all(row)]
    return [cols*[0] for i in range(rows - len(new_bitmap))] + new_bitmap

  def size(self):
    return (len(self.bitmap), len(self.bitmap[0]))

  def num_holes(self):
    (rows, cols) = self.size()
    holes = 0
    # Counts any overhang as a hole. This is pessimistic, but should work
    # reasonably well.
    column_occupied = cols*[0]
    for row in range(0, rows):
      for col in range(0, cols):
        if self.bitmap[row][col] == 0:
          if column_occupied[col]:
            holes += 1
        else:
          column_occupied[col] += 1
    return holes

  def col_height(self, col):
    (rows, _) = self.size()
    for row in range(0, rows):
      if self.bitmap[row][col] != 0:
        return rows - row
    return 0

  def max_height(self):
    (rows, cols) = self.size()
    m_height = 0
    for col in range(0, cols):
      m_height = max(m_height, self.col_height(col))
    return m_height

  def height_variance(self):
    (rows, cols) = self.size()
    variance = 0
    prev = self.col_height(0)
    for col in range(0, cols):
      cur = self.col_height(col)
      variance += abs(cur - prev)
      prev = cur
    return variance

  def height_penalty(self):
    (rows, cols) = self.size()
    penalty = 0
    for row in range(0, rows):
      for col in range(0, cols):
        if self.bitmap[row][col] != 0:
          penalty += rows - row
    return penalty

  def evaluate(self):
    return -self.num_holes() - self.max_height() \
      - self.height_variance()# - self.height_penalty()

test_board = Board([[1, 1, 1], [1, 0, 1], [1, 1, 1]], None, None)
print test_board.num_holes()
print test_board.max_height()
print test_board.height_variance()
print test_board.height_penalty()

if __name__ == '__main__':
  if len(sys.argv) == 3:
    # This AI executable will be called with two arguments: a JSON blob of the
    # game state and the number of seconds remaining in this game.
    seconds_left = float(sys.argv[2])

    # current board
    board = Board.construct_from_json(sys.argv[1])

    # current block
    block = board.block

    best = -sys.maxint - 1
    choices = {}
    for i in range(0, 12):
      moves = []
      while block.checked_left(board):
        moves.append('left')
      for _ in range(0, i):
        moves.append('right')
      while block.checked_down(board):
        moves.append('down')

      for _ in xrange(0, 3):
        moves.append('rotate')
        block.reset_position()
        try:
          new_board = board.do_commands(moves[:])
          cur = new_board.evaluate()
          choices[cur] = moves[:]
        except InvalidMoveError as e:
          continue

    todo = choices[max(choices)]
    print '\n'.join(todo)
    sys.stdout.flush()
