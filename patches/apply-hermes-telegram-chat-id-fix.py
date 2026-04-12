from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Could not find expected Telegram block: {label}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hermes-telegram-chat-id-fix.py <hermes-repo>")

    repo = Path(sys.argv[1])
    telegram_path = repo / "gateway" / "platforms" / "telegram.py"
    send_tool_path = repo / "tools" / "send_message_tool.py"
    text = telegram_path.read_text()
    send_tool_text = send_tool_path.read_text()

    if (
        "def _normalize_chat_id(chat_id: Any) -> Any:" in text
        and "def _normalize_telegram_chat_id(chat_id):" in send_tool_text
    ):
        print("Telegram chat_id fixes already present; skipping patch")
        return 0

    text = replace_once(
        text,
        """        else:  # \"first\" (default)\n            return chunk_index == 0\n\n    async def send(\n""",
        """        else:  # \"first\" (default)\n            return chunk_index == 0\n\n    @staticmethod\n    def _normalize_chat_id(chat_id: Any) -> Any:\n        \"\"\"Convert numeric chat IDs to ints while preserving string targets.\"\"\"\n        if chat_id is None or isinstance(chat_id, int):\n            return chat_id\n\n        normalized = str(chat_id).strip()\n        if re.fullmatch(r\"-?\\d+\", normalized):\n            return int(normalized)\n        return normalized\n\n    async def send(\n""",
        "insert helper",
    )

    text = replace_once(
        text,
        """            message_ids = []\n            thread_id = metadata.get(\"thread_id\") if metadata else None\n            \n            try:\n""",
        """            message_ids = []\n            thread_id = metadata.get(\"thread_id\") if metadata else None\n            target_chat_id = self._normalize_chat_id(chat_id)\n            \n            try:\n""",
        "send target chat id",
    )
    text = replace_once(
        text,
        """                            msg = await self._bot.send_message(\n                                chat_id=int(chat_id),\n""",
        """                            msg = await self._bot.send_message(\n                                chat_id=target_chat_id,\n""",
        "send markdown path",
    )
    text = replace_once(
        text,
        """                                msg = await self._bot.send_message(\n                                    chat_id=int(chat_id),\n""",
        """                                msg = await self._bot.send_message(\n                                    chat_id=target_chat_id,\n""",
        "send plain-text fallback",
    )

    text = replace_once(
        text,
        """        if not self._bot:\n            return SendResult(success=False, error=\"Not connected\")\n        try:\n            formatted = self.format_message(content)\n""",
        """        if not self._bot:\n            return SendResult(success=False, error=\"Not connected\")\n        try:\n            target_chat_id = self._normalize_chat_id(chat_id)\n            formatted = self.format_message(content)\n""",
        "edit target chat id",
    )
    text = replace_once(
        text,
        """                await self._bot.edit_message_text(\n                    chat_id=int(chat_id),\n                    message_id=int(message_id),\n                    text=formatted,\n                    parse_mode=ParseMode.MARKDOWN_V2,\n                )\n""",
        """                await self._bot.edit_message_text(\n                    chat_id=target_chat_id,\n                    message_id=int(message_id),\n                    text=formatted,\n                    parse_mode=ParseMode.MARKDOWN_V2,\n                )\n""",
        "edit markdown path",
    )
    text = replace_once(
        text,
        """                await self._bot.edit_message_text(\n                    chat_id=int(chat_id),\n                    message_id=int(message_id),\n                    text=content,\n                )\n""",
        """                await self._bot.edit_message_text(\n                    chat_id=target_chat_id,\n                    message_id=int(message_id),\n                    text=content,\n                )\n""",
        "edit plain fallback",
    )
    text = replace_once(
        text,
        """                    await self._bot.edit_message_text(\n                        chat_id=int(chat_id),\n                        message_id=int(message_id),\n                        text=truncated,\n                    )\n""",
        """                    await self._bot.edit_message_text(\n                        chat_id=target_chat_id,\n                        message_id=int(message_id),\n                        text=truncated,\n                    )\n""",
        "edit truncation fallback",
    )
    text = replace_once(
        text,
        """                    await self._bot.edit_message_text(\n                        chat_id=int(chat_id),\n                        message_id=int(message_id),\n                        text=content,\n                    )\n""",
        """                    await self._bot.edit_message_text(\n                        chat_id=target_chat_id,\n                        message_id=int(message_id),\n                        text=content,\n                    )\n""",
        "edit flood retry",
    )

    text = replace_once(
        text,
        """            msg = await self._bot.send_message(\n                chat_id=int(chat_id),\n                text=text,\n                parse_mode=ParseMode.MARKDOWN,\n                reply_markup=keyboard,\n            )\n""",
        """            msg = await self._bot.send_message(\n                chat_id=self._normalize_chat_id(chat_id),\n                text=text,\n                parse_mode=ParseMode.MARKDOWN,\n                reply_markup=keyboard,\n            )\n""",
        "update prompt send",
    )

    text = replace_once(
        text,
        """            kwargs: Dict[str, Any] = {\n                \"chat_id\": int(chat_id),\n                \"text\": text,\n                \"parse_mode\": ParseMode.MARKDOWN,\n                \"reply_markup\": keyboard,\n            }\n""",
        """            kwargs: Dict[str, Any] = {\n                \"chat_id\": self._normalize_chat_id(chat_id),\n                \"text\": text,\n                \"parse_mode\": ParseMode.MARKDOWN,\n                \"reply_markup\": keyboard,\n            }\n""",
        "exec approval send",
    )

    text = replace_once(
        text,
        """            msg = await self._bot.send_message(\n                chat_id=int(chat_id),\n                text=text,\n                parse_mode=ParseMode.MARKDOWN,\n                reply_markup=keyboard,\n                message_thread_id=int(thread_id) if thread_id else None,\n            )\n""",
        """            msg = await self._bot.send_message(\n                chat_id=self._normalize_chat_id(chat_id),\n                text=text,\n                parse_mode=ParseMode.MARKDOWN,\n                reply_markup=keyboard,\n                message_thread_id=int(thread_id) if thread_id else None,\n            )\n""",
        "model picker send",
    )

    text = replace_once(
        text,
        """        try:\n            import os\n            if not os.path.exists(audio_path):\n                return SendResult(success=False, error=f\"Audio file not found: {audio_path}\")\n            \n            with open(audio_path, \"rb\") as audio_file:\n""",
        """        try:\n            import os\n            if not os.path.exists(audio_path):\n                return SendResult(success=False, error=f\"Audio file not found: {audio_path}\")\n            \n            target_chat_id = self._normalize_chat_id(chat_id)\n\n            with open(audio_path, \"rb\") as audio_file:\n""",
        "voice target chat id",
    )
    text = replace_once(
        text,
        """                    msg = await self._bot.send_voice(\n                        chat_id=int(chat_id),\n                        voice=audio_file,\n""",
        """                    msg = await self._bot.send_voice(\n                        chat_id=target_chat_id,\n                        voice=audio_file,\n""",
        "voice send",
    )
    text = replace_once(
        text,
        """                    msg = await self._bot.send_audio(\n                        chat_id=int(chat_id),\n                        audio=audio_file,\n""",
        """                    msg = await self._bot.send_audio(\n                        chat_id=target_chat_id,\n                        audio=audio_file,\n""",
        "audio send",
    )

    text = replace_once(
        text,
        """            _thread = metadata.get(\"thread_id\") if metadata else None\n            with open(image_path, \"rb\") as image_file:\n""",
        """            _thread = metadata.get(\"thread_id\") if metadata else None\n            target_chat_id = self._normalize_chat_id(chat_id)\n            with open(image_path, \"rb\") as image_file:\n""",
        "image file target chat id",
    )
    text = replace_once(
        text,
        """                msg = await self._bot.send_photo(\n                    chat_id=int(chat_id),\n                    photo=image_file,\n""",
        """                msg = await self._bot.send_photo(\n                    chat_id=target_chat_id,\n                    photo=image_file,\n""",
        "image file send",
    )

    text = replace_once(
        text,
        """            display_name = file_name or os.path.basename(file_path)\n            _thread = metadata.get(\"thread_id\") if metadata else None\n\n            with open(file_path, \"rb\") as f:\n""",
        """            display_name = file_name or os.path.basename(file_path)\n            _thread = metadata.get(\"thread_id\") if metadata else None\n            target_chat_id = self._normalize_chat_id(chat_id)\n\n            with open(file_path, \"rb\") as f:\n""",
        "document target chat id",
    )
    text = replace_once(
        text,
        """                msg = await self._bot.send_document(\n                    chat_id=int(chat_id),\n                    document=f,\n""",
        """                msg = await self._bot.send_document(\n                    chat_id=target_chat_id,\n                    document=f,\n""",
        "document send",
    )

    text = replace_once(
        text,
        """            _thread = metadata.get(\"thread_id\") if metadata else None\n            with open(video_path, \"rb\") as f:\n""",
        """            _thread = metadata.get(\"thread_id\") if metadata else None\n            target_chat_id = self._normalize_chat_id(chat_id)\n            with open(video_path, \"rb\") as f:\n""",
        "video target chat id",
    )
    text = replace_once(
        text,
        """                msg = await self._bot.send_video(\n                    chat_id=int(chat_id),\n                    video=f,\n""",
        """                msg = await self._bot.send_video(\n                    chat_id=target_chat_id,\n                    video=f,\n""",
        "video send",
    )

    text = replace_once(
        text,
        """        try:\n            # Telegram can send photos directly from URLs (up to ~5MB)\n            _photo_thread = metadata.get(\"thread_id\") if metadata else None\n            msg = await self._bot.send_photo(\n                chat_id=int(chat_id),\n""",
        """        try:\n            # Telegram can send photos directly from URLs (up to ~5MB)\n            _photo_thread = metadata.get(\"thread_id\") if metadata else None\n            target_chat_id = self._normalize_chat_id(chat_id)\n            msg = await self._bot.send_photo(\n                chat_id=target_chat_id,\n""",
        "image target chat id",
    )
    text = replace_once(
        text,
        """                msg = await self._bot.send_photo(\n                    chat_id=int(chat_id),\n""",
        """                msg = await self._bot.send_photo(\n                    chat_id=target_chat_id,\n""",
        "image upload fallback",
    )

    text = replace_once(
        text,
        """            msg = await self._bot.send_animation(\n                chat_id=int(chat_id),\n""",
        """            msg = await self._bot.send_animation(\n                chat_id=self._normalize_chat_id(chat_id),\n""",
        "animation send",
    )

    text = replace_once(
        text,
        """                await self._bot.send_chat_action(\n                    chat_id=int(chat_id),\n""",
        """                await self._bot.send_chat_action(\n                    chat_id=self._normalize_chat_id(chat_id),\n""",
        "typing indicator",
    )

    text = replace_once(
        text,
        """        try:\n            chat = await self._bot.get_chat(int(chat_id))\n""",
        """        try:\n            chat = await self._bot.get_chat(self._normalize_chat_id(chat_id))\n""",
        "get chat info",
    )

    text = replace_once(
        text,
        """            await self._bot.set_message_reaction(\n                chat_id=int(chat_id),\n""",
        """            await self._bot.set_message_reaction(\n                chat_id=self._normalize_chat_id(chat_id),\n""",
        "message reaction",
    )

    send_tool_text = replace_once(
        send_tool_text,
        """def _error(message: str) -> dict:\n    \"\"\"Build a standardized error payload with redacted content.\"\"\"\n    return {\"error\": _sanitize_error_text(message)}\n\n\nSEND_MESSAGE_SCHEMA = {\n""",
        """def _error(message: str) -> dict:\n    \"\"\"Build a standardized error payload with redacted content.\"\"\"\n    return {\"error\": _sanitize_error_text(message)}\n\n\ndef _normalize_telegram_chat_id(chat_id):\n    \"\"\"Convert numeric Telegram chat IDs to ints while preserving string targets.\"\"\"\n    if chat_id is None or isinstance(chat_id, int):\n        return chat_id\n\n    normalized = str(chat_id).strip()\n    if re.fullmatch(r\"-?\\d+\", normalized):\n        return int(normalized)\n    return normalized\n\n\nSEND_MESSAGE_SCHEMA = {\n""",
        "send_message_tool helper",
    )
    send_tool_text = replace_once(
        send_tool_text,
        "int_chat_id = int(chat_id)\n",
        "telegram_chat_id = _normalize_telegram_chat_id(chat_id)\n",
        "send_message_tool target id",
    )
    send_tool_text = send_tool_text.replace(
        "chat_id=int_chat_id", "chat_id=telegram_chat_id"
    )

    telegram_path.write_text(text)
    send_tool_path.write_text(send_tool_text)
    print(f"Applied Telegram chat_id fix to {telegram_path}")
    print(f"Applied Telegram chat_id fix to {send_tool_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
