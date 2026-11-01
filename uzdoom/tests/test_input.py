# SPDX-License-Identifier: GPL-3.0-or-later
"""Movement recovery must preserve attack/use press-edge behavior."""
import threading,unittest
from unittest.mock import Mock,patch
from uzdoom.game import Game
from uzdoom.engine import KEYS


class InputContract(unittest.TestCase):
    def test_reassert_movement_without_repeating_actions(self):
        game=Game.__new__(Game);game.lock=threading.RLock();game.owner='test';game.state={'level_tics':3};game.engine=Mock()
        game.held=set();game.motion_rearm_tick=7
        keys=['KeyW','KeyF','MouseFire']
        with patch('uzdoom.game.time.monotonic',return_value=100):game.input('test',keys)
        first=list(game.engine.key.call_args_list);self.assertEqual({args.args for args in first},{(KEYS[k],True) for k in ('KeyF','MouseFire')})
        game.engine.key.reset_mock()
        game.state['level_tics']=10
        with patch('uzdoom.game.time.monotonic',return_value=100.2):game.input('test',keys)
        game.engine.key.assert_called_once_with(KEYS['KeyW'],True)
        game.engine.key.reset_mock()
        with patch('uzdoom.game.time.monotonic',return_value=100.3):game.input('test',[],paused=True)
        self.assertEqual({args.args for args in game.engine.key.call_args_list},{(KEYS[k],False) for k in keys})
        self.assertIsNone(game.owner);self.assertFalse(game.held)


if __name__=='__main__':unittest.main()
