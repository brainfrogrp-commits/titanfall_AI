"""Run with:  python -m unittest discover -s tests   (from the app folder)"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bt_voice import config, slurs, twitch  # noqa: E402

NWORD = "nigger"  # the word the Pilot named; every other word is exercised from the built-in list


def privmsg(login, text, msg_id="m1", name=None):
    tags = f"display-name={name or login};emotes=;id={msg_id};user-id=7"
    return f"@{tags} :{login}!{login}@{login}.tmi.twitch.tv PRIVMSG #brainfrog :{text}"


def fresh_chat(**kw):
    chat = twitch.TwitchChat()
    chat.channel = "brainfrog"
    chat.ignore = []
    chat.blocked = kw.get("blocked", [])
    chat.filter_slurs = kw.get("filter_slurs", True)
    return chat


class Evasions(unittest.TestCase):
    def test_the_named_word_is_caught_in_its_disguises(self):
        disguises = [
            NWORD, NWORD.upper(), NWORD.title(), "what a " + NWORD + " lol", NWORD + "s", NWORD + "rrr",
            "n1gger", "n!gg3r", "n1gg3r", "n|gger",
            "n i g g e r", "n.i.g.g.e.r", "n-i-g-g-e-r", "n_i_g_g_e_r",
            "niggggger", "nnniiiggggeeerrr",
            "ｎｉｇｇｅｒ",                      # full-width letters
            "nìgger", "nîggér",                 # accents
            "nіgger", "nigɡer".replace("ɡ", "g"),  # Cyrillic і
            "nig​ger",                     # an invisible character inside
            "nigga", "NIGGA", "n1gga", "n i g g a", "niggas", "niggaz", "niggah",
        ]
        for text in disguises:
            self.assertTrue(slurs.contains_slur(text), repr(text))

    def test_innocent_words_that_share_letters_are_not_caught(self):
        for text in ("snigger", "sniggering", "he sniggered at it", "Niger", "Nigeria", "Nigerian food",
                     "the niger river", "niggardly", "a niggling doubt", "anniversary", "ignore this",
                     "great stream", "nice game", "I love this boss fight"):
            self.assertFalse(slurs.contains_slur(text), text)

    def test_every_built_in_word_is_caught_plain_loud_and_with_symbols(self):
        for word in slurs.builtin_words():
            self.assertTrue(slurs.contains_slur(word), "plain")
            self.assertTrue(slurs.contains_slur(f"you are a {word.upper()}!"), "inside a sentence")
            self.assertTrue(slurs.contains_slur(word.replace("i", "1").replace("e", "3").replace("a", "4")
                                                .replace("o", "0")), "symbols")

    def test_short_words_are_only_caught_as_whole_words(self):
        for word in slurs.builtin_words():
            if len(word) <= 5 and word != slurs.codecs.decode("avttn", "rot13"):
                self.assertFalse(slurs.contains_slur("the " + word + "xyz is fine"), word)
                self.assertFalse(slurs.contains_slur("xyz" + word), word)

    def test_ordinary_chat_passes(self):
        for text in ("hey BT, how are you?", "that Titan fight was insane", "pog", "can you read my name out",
                     "kind of a bike race", "spice it up", "raccoon", "Pakistan", "I like cigarettes and cheese"):
            self.assertFalse(slurs.contains_slur(text), text)

    def test_none_and_empty_are_safe(self):
        self.assertFalse(slurs.contains_slur(""))
        self.assertFalse(slurs.contains_slur(None))


class CustomWords(unittest.TestCase):
    def test_whole_words_with_symbols_and_stretching(self):
        for text in ("this is baaad", "b4d word here", "BAD!", "bad, really"):
            self.assertTrue(slurs.matches_any(text, ["bad"]), text)

    def test_parts_of_other_words_are_left_alone(self):
        self.assertFalse(slurs.matches_any("badminton and badger", ["bad"]))

    def test_phrases_and_empty_entries(self):
        self.assertTrue(slurs.matches_any("you are a Bad  Person", ["bad person"]))
        self.assertFalse(slurs.matches_any("anything at all", ["", "  ", "!!"]))


class InChat(unittest.TestCase):
    def kept(self, chat):
        return [m.text for m in chat.recent(10)]

    def test_a_message_with_a_slur_is_dropped_and_counted(self):
        chat = fresh_chat()
        chat.handle_line(privmsg("a", "hello chat", msg_id="1"))
        chat.handle_line(privmsg("b", "you are a " + NWORD, msg_id="2"))
        chat.handle_line(privmsg("c", "you are a n!gg3r", msg_id="3"))
        chat.handle_line(privmsg("d", "nice stream", msg_id="4"))
        self.assertEqual(self.kept(chat), ["hello chat", "nice stream"])
        self.assertEqual(chat.status()["filtered"], 2)

    def test_a_slur_in_the_username_drops_the_message(self):
        chat = fresh_chat()
        chat.handle_line(privmsg("x", "totally polite message", msg_id="1", name=NWORD + "_fan"))
        chat.handle_line(privmsg("ok_user", "another polite message", msg_id="2"))
        self.assertEqual(self.kept(chat), ["another polite message"])

    def test_turning_the_filter_off_is_respected(self):
        chat = fresh_chat(filter_slurs=False)
        chat.handle_line(privmsg("b", "hello " + NWORD, msg_id="1"))
        self.assertEqual(len(chat.recent(5)), 1)

    def test_the_setting_reaches_the_connection_and_defaults_on(self):
        self.assertTrue(config.DEFAULTS["twitch_filter_slurs"])
        chat = twitch.TwitchChat()
        chat.apply(dict(config.DEFAULTS, twitch_enabled=False, twitch_filter_slurs=False))
        self.assertFalse(chat.filter_slurs)

    def test_custom_blocked_words_count_too(self):
        chat = fresh_chat(blocked=["spoilerword"])
        chat.handle_line(privmsg("a", "SP0ILERWORD incoming", msg_id="1"))
        chat.handle_line(privmsg("b", "all good", msg_id="2"))
        self.assertEqual(self.kept(chat), ["all good"])
        self.assertEqual(chat.status()["filtered"], 1)

    def test_the_source_file_does_not_spell_the_words_out(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "bt_voice", "slurs.py"), encoding="utf-8") as f:
            source = f.read().lower()
        for word in slurs.builtin_words():
            if len(word) > 4:
                self.assertNotIn(word, source)


if __name__ == "__main__":
    unittest.main()
