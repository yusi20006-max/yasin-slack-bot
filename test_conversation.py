import unittest

from conversation import ConversationStore


class ConversationStoreTests(unittest.TestCase):
    def test_top_level_messages_share_channel_context(self):
        store = ConversationStore(max_messages=4)
        store.append("C1", None, "user", "My project is YasinHub")
        store.append("C1", None, "model", "Got it")
        history = store.get("C1")
        self.assertEqual([item["role"] for item in history], ["user", "model"])
        self.assertIn("YasinHub", history[0]["parts"][0]["text"])

    def test_threads_are_isolated(self):
        store = ConversationStore()
        store.append("C1", "100.1", "user", "thread one")
        store.append("C1", "200.2", "user", "thread two")
        self.assertEqual(store.size("C1", "100.1"), 1)
        self.assertEqual(store.size("C1", "200.2"), 1)
        self.assertEqual(store.size("C1"), 0)

    def test_channels_are_isolated(self):
        store = ConversationStore()
        store.append("C1", None, "user", "private to C1")
        self.assertEqual(store.size("C1"), 1)
        self.assertEqual(store.size("C2"), 0)

    def test_history_is_bounded(self):
        store = ConversationStore(max_messages=3)
        for index in range(5):
            store.append("C1", None, "user", f"message {index}")
        history = store.get("C1")
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["parts"][0]["text"], "message 2")
        self.assertEqual(history[-1]["parts"][0]["text"], "message 4")

    def test_invalid_role_is_rejected(self):
        store = ConversationStore()
        with self.assertRaises(ValueError):
            store.append("C1", None, "assistant", "bad role")


if __name__ == "__main__":
    unittest.main()
