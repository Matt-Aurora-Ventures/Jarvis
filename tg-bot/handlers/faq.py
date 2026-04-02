"""
FAQ Command Handler for Telegram Bot.

Provides FAQ display, search, and management functionality.
Supports:
- Listing all FAQs
- Viewing specific FAQ by ID
- Category filtering
- Keyword search with fuzzy matching
- Admin CRUD operations (add, update, delete, reorder)
- Inline button navigation
- Pagination for large FAQ lists
"""

import html
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from tg_bot.handlers import admin_only, error_handler

logger = logging.getLogger(__name__)

# Configuration
FAQS_PER_PAGE = 5
MAX_ANSWER_LENGTH = 3500  # Leave room for formatting
FAQ_DATA_FILE = Path(__file__).parent.parent.parent / "lifeos" / "config" / "faqs.json"

# Singleton instance
_faq_store: Optional["FAQStore"] = None


class FAQStore:
    """In-memory FAQ storage with persistence to JSON file."""

    def __init__(self, data_file: Optional[Path] = None):
        """Initialize FAQ store.

        Args:
            data_file: Path to JSON file for persistence. Defaults to FAQ_DATA_FILE.
        """
        self._faqs: List[Dict[str, Any]] = []
        self._data_file = data_file or FAQ_DATA_FILE
        self._load()

    def _load(self) -> None:
        """Load FAQs from JSON file."""
        try:
            if self._data_file.exists():
                with open(self._data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._faqs = data.get("faqs", [])
                    logger.info(f"Loaded {len(self._faqs)} FAQs from {self._data_file}")
            else:
                self._faqs = self._get_default_faqs()
                self._save()
                logger.info(f"Created default FAQs at {self._data_file}")
        except Exception as e:
            logger.error(f"Error loading FAQs: {e}")
            self._faqs = self._get_default_faqs()

    def _save(self) -> None:
        """Save FAQs to JSON file."""
        try:
            self._data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump({"faqs": self._faqs}, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(self._faqs)} FAQs to {self._data_file}")
        except Exception as e:
            logger.error(f"Error saving FAQs: {e}")

    def _get_default_faqs(self) -> List[Dict[str, Any]]:
        """Return default FAQs for initial setup."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                "id": 1,
                "question": "What is Jarvis?",
                "answer": "Jarvis is an AI-powered trading assistant for Solana tokens. It helps you analyze tokens, track your portfolio, and make informed trading decisions.",
                "category": "general",
                "keywords": ["jarvis", "what", "about", "introduction"],
                "order": 1,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 2,
                "question": "How do I start trading?",
                "answer": "Use `/balance` to check your wallet balance, then `/buy <token> <amount>` to make a trade. Use `/analyze <token>` first to get AI insights!",
                "category": "trading",
                "keywords": ["trading", "start", "begin", "buy", "how"],
                "order": 2,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 3,
                "question": "What are the fees?",
                "answer": "There are no fees for using Jarvis. You only pay standard Solana network fees (typically less than $0.01 per transaction).",
                "category": "trading",
                "keywords": ["fees", "cost", "price", "charges"],
                "order": 3,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 4,
                "question": "How do I contact support?",
                "answer": "Contact @matthaynes88 on Telegram for support, or use the `/help` command to see available commands.",
                "category": "support",
                "keywords": ["support", "help", "contact", "issue"],
                "order": 4,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 5,
                "question": "Is my wallet safe?",
                "answer": "Yes! Jarvis never stores your private keys. All transactions require your explicit approval. Your funds remain in your control at all times.",
                "category": "security",
                "keywords": ["security", "safe", "wallet", "keys", "private"],
                "order": 5,
                "created_at": now,
                "updated_at": now,
            },
        ]

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all FAQs sorted by order."""
        return sorted(self._faqs, key=lambda f: f.get("order", 999))

    def get_by_id(self, faq_id: int) -> Optional[Dict[str, Any]]:
        """Get FAQ by ID."""
        return next((f for f in self._faqs if f["id"] == faq_id), None)

    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get FAQs by category."""
        return [f for f in self._faqs if f.get("category", "").lower() == category.lower()]

    def get_categories(self) -> List[str]:
        """Get unique category names."""
        categories = set()
        for faq in self._faqs:
            if cat := faq.get("category"):
                categories.add(cat.lower())
        return sorted(categories)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search FAQs by query with fuzzy matching.

        Searches question, answer, and keywords.
        Returns results sorted by relevance.
        """
        query_lower = query.lower()
        results: List[Tuple[Dict[str, Any], int]] = []

        for faq in self._faqs:
            score = 0

            # Exact match in question (highest priority)
            if query_lower in faq.get("question", "").lower():
                score += 100
                if query_lower == faq.get("question", "").lower():
                    score += 50  # Exact match bonus

            # Match in answer
            if query_lower in faq.get("answer", "").lower():
                score += 50

            # Match in keywords
            keywords = faq.get("keywords", [])
            for keyword in keywords:
                if query_lower in keyword.lower():
                    score += 75
                elif keyword.lower() in query_lower:
                    score += 25  # Partial keyword match

            # Fuzzy match - query is substring of question/answer words
            question_words = faq.get("question", "").lower().split()
            answer_words = faq.get("answer", "").lower().split()

            for word in question_words:
                if word.startswith(query_lower) or query_lower.startswith(word):
                    score += 10

            for word in answer_words:
                if word.startswith(query_lower) or query_lower.startswith(word):
                    score += 5

            if score > 0:
                results.append((faq, score))

        # Sort by score descending, then by order
        results.sort(key=lambda x: (-x[1], x[0].get("order", 999)))
        return [r[0] for r in results]

    def add(
        self,
        question: str,
        answer: str,
        category: str = "general",
        keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Add new FAQ."""
        now = datetime.now(timezone.utc).isoformat()

        # Generate new ID
        max_id = max((f["id"] for f in self._faqs), default=0)
        new_id = max_id + 1

        # Get next order
        max_order = max((f.get("order", 0) for f in self._faqs), default=0)

        new_faq = {
            "id": new_id,
            "question": question,
            "answer": answer,
            "category": category,
            "keywords": keywords or [],
            "order": max_order + 1,
            "created_at": now,
            "updated_at": now,
        }

        self._faqs.append(new_faq)
        self._save()
        logger.info(f"Added FAQ {new_id}: {question[:50]}...")

        return new_faq

    def update(self, faq_id: int, **kwargs) -> bool:
        """Update existing FAQ.

        Args:
            faq_id: ID of FAQ to update
            **kwargs: Fields to update (question, answer, category, keywords)

        Returns:
            True if updated, False if not found
        """
        faq = self.get_by_id(faq_id)
        if not faq:
            return False

        # Update allowed fields
        allowed_fields = {"question", "answer", "category", "keywords", "order"}
        for key, value in kwargs.items():
            if key in allowed_fields:
                faq[key] = value

        faq["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._save()
        logger.info(f"Updated FAQ {faq_id}")
        return True

    def delete(self, faq_id: int) -> bool:
        """Delete FAQ by ID.

        Returns:
            True if deleted, False if not found
        """
        faq = self.get_by_id(faq_id)
        if not faq:
            return False

        self._faqs.remove(faq)
        self._save()
        logger.info(f"Deleted FAQ {faq_id}")
        return True

    def reorder(self, faq_id: int, new_position: int) -> bool:
        """Move FAQ to new position.

        Args:
            faq_id: ID of FAQ to move
            new_position: New order position (1-based)

        Returns:
            True if reordered, False if not found
        """
        faq = self.get_by_id(faq_id)
        if not faq:
            return False

        # Get all FAQs sorted by current order
        all_faqs = self.get_all()

        # Remove the FAQ from its current position
        all_faqs = [f for f in all_faqs if f["id"] != faq_id]

        # Insert at new position (1-based to 0-based)
        insert_idx = max(0, min(new_position - 1, len(all_faqs)))
        all_faqs.insert(insert_idx, faq)

        # Update order values
        for idx, f in enumerate(all_faqs):
            f["order"] = idx + 1

        self._save()
        logger.info(f"Reordered FAQ {faq_id} to position {new_position}")
        return True


def get_faq_store() -> FAQStore:
    """Get singleton FAQ store instance."""
    global _faq_store
    if _faq_store is None:
        _faq_store = FAQStore()
    return _faq_store


def _format_faq_list(faqs: List[Dict[str, Any]], page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    """Format FAQ list with pagination.

    Args:
        faqs: List of FAQs to display
        page: Current page number (0-based)

    Returns:
        Tuple of (message text, inline keyboard)
    """
    if not faqs:
        return (
            "<b>Frequently Asked Questions</b>\n\n"
            "<i>No FAQs available.</i>",
            InlineKeyboardMarkup([])
        )

    total_pages = (len(faqs) + FAQS_PER_PAGE - 1) // FAQS_PER_PAGE
    page = max(0, min(page, total_pages - 1))

    start_idx = page * FAQS_PER_PAGE
    end_idx = start_idx + FAQS_PER_PAGE
    page_faqs = faqs[start_idx:end_idx]

    lines = ["<b>Frequently Asked Questions</b>", ""]

    for faq in page_faqs:
        question = html.escape(faq.get("question", ""))
        category = html.escape(faq.get("category", "general"))
        faq_id = faq.get("id", 0)

        lines.append(f"<b>{faq_id}.</b> {question}")
        lines.append(f"   <i>[{category}]</i>")
        lines.append("")

    if total_pages > 1:
        lines.append(f"<i>Page {page + 1} of {total_pages}</i>")

    # Build keyboard
    buttons: List[List[InlineKeyboardButton]] = []

    # FAQ selection buttons
    for faq in page_faqs:
        faq_id = faq.get("id", 0)
        question = faq.get("question", "")[:30] + "..." if len(faq.get("question", "")) > 30 else faq.get("question", "")
        buttons.append([
            InlineKeyboardButton(f"{faq_id}. {question}", callback_data=f"faq:show:{faq_id}")
        ])

    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("< Prev", callback_data=f"faq:page:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next >", callback_data=f"faq:page:{page + 1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    # Category filter buttons
    store = get_faq_store()
    categories = store.get_categories()
    if categories:
        cat_buttons = [
            InlineKeyboardButton(cat.capitalize(), callback_data=f"faq:category:{cat}")
            for cat in categories[:4]  # Limit to 4 categories per row
        ]
        buttons.append(cat_buttons)

    return "\n".join(lines), InlineKeyboardMarkup(buttons)


def _format_faq_detail(faq: Dict[str, Any], total_count: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    """Format single FAQ detail view.

    Args:
        faq: FAQ dict to display
        total_count: Total number of FAQs (for navigation)

    Returns:
        Tuple of (message text, inline keyboard)
    """
    faq_id = faq.get("id", 0)
    question = html.escape(faq.get("question", ""))
    answer = faq.get("answer", "")
    category = html.escape(faq.get("category", "general"))

    # Truncate long answers
    if len(answer) > MAX_ANSWER_LENGTH:
        answer = answer[:MAX_ANSWER_LENGTH] + "..."

    # Escape HTML but preserve code formatting
    answer = html.escape(answer)
    # Restore code blocks
    answer = re.sub(r'`([^`]+)`', r'<code>\1</code>', answer)

    lines = [
        f"<b>FAQ #{faq_id}</b>",
        "",
        f"<b>Q:</b> {question}",
        "",
        f"<b>A:</b> {answer}",
        "",
        f"<i>Category: {category}</i>",
    ]

    # Navigation buttons
    buttons: List[List[InlineKeyboardButton]] = []

    nav_buttons = []
    if faq_id > 1:
        nav_buttons.append(InlineKeyboardButton("< Previous", callback_data=f"faq:prev:{faq_id}"))
    if total_count > 0 and faq_id < total_count:
        nav_buttons.append(InlineKeyboardButton("Next >", callback_data=f"faq:next:{faq_id}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton("Back to List", callback_data="faq:list:0")])

    return "\n".join(lines), InlineKeyboardMarkup(buttons)


@error_handler
async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /faq command.

    Usage:
        /faq - List all FAQs
        /faq <id> - Show specific FAQ
        /faq <search> - Search FAQs
        /faq --category <cat> - Filter by category
        /faq --categories - List categories
    """
    if not update.message:
        return

    store = get_faq_store()
    args = context.args or []

    try:
        # Parse arguments
        if not args:
            # List all FAQs
            faqs = store.get_all()
            text, keyboard = _format_faq_list(faqs, page=0)
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return

        # Check for flags
        if "--categories" in args:
            categories = store.get_categories()
            if categories:
                text = "<b>FAQ Categories</b>\n\n" + "\n".join(f"- {cat.capitalize()}" for cat in categories)
            else:
                text = "<b>FAQ Categories</b>\n\n<i>No categories available.</i>"
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            return

        if "--category" in args:
            try:
                cat_idx = args.index("--category")
                category = args[cat_idx + 1] if cat_idx + 1 < len(args) else ""
                faqs = store.get_by_category(category)
                if not faqs:
                    await update.message.reply_text(
                        f"<i>No FAQs found in category '{html.escape(category)}'.</i>",
                        parse_mode=ParseMode.HTML
                    )
                    return
                text, keyboard = _format_faq_list(faqs, page=0)
                await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
                return
            except (IndexError, ValueError):
                await update.message.reply_text(
                    "Usage: /faq --category <category_name>",
                    parse_mode=ParseMode.HTML
                )
                return

        # Try to parse as FAQ ID
        try:
            faq_id = int(args[0])
            faq = store.get_by_id(faq_id)
            if faq:
                text, keyboard = _format_faq_detail(faq, len(store.get_all()))
                await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                await update.message.reply_text(
                    f"<i>FAQ #{faq_id} not found.</i>",
                    parse_mode=ParseMode.HTML
                )
            return
        except ValueError:
            pass  # Not a number, treat as search query

        # Search FAQs
        query = " ".join(args)
        faqs = store.search(query)
        if faqs:
            text, keyboard = _format_faq_list(faqs, page=0)
            text = f"<b>Search Results for '{html.escape(query)}'</b>\n\n" + text.split("\n\n", 1)[1]
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        else:
            await update.message.reply_text(
                f"<i>No FAQs found matching '{html.escape(query)}'.</i>",
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        logger.exception(f"Error in faq_command: {e}")
        await update.message.reply_text(
            "Sorry, an error occurred while loading FAQs. Please try again.",
            parse_mode=ParseMode.HTML
        )


@error_handler
async def handle_faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle FAQ inline button callbacks.

    Callback data formats:
        faq:list:<page> - Show FAQ list at page
        faq:show:<id> - Show specific FAQ
        faq:page:<page> - Navigate to page
        faq:category:<cat> - Filter by category
        faq:next:<id> - Show next FAQ
        faq:prev:<id> - Show previous FAQ
    """
    query = update.callback_query
    if not query:
        return

    await query.answer()

    data = query.data or ""
    if not data.startswith("faq:"):
        return

    store = get_faq_store()
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    param = parts[2] if len(parts) > 2 else ""

    try:
        if action == "list":
            page = int(param) if param else 0
            faqs = store.get_all()
            text, keyboard = _format_faq_list(faqs, page=page)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif action == "show":
            faq_id = int(param)
            faq = store.get_by_id(faq_id)
            if faq:
                text, keyboard = _format_faq_detail(faq, len(store.get_all()))
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                await query.edit_message_text(f"<i>FAQ #{faq_id} not found.</i>", parse_mode=ParseMode.HTML)

        elif action == "page":
            page = int(param)
            faqs = store.get_all()
            text, keyboard = _format_faq_list(faqs, page=page)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif action == "category":
            category = param
            faqs = store.get_by_category(category)
            if faqs:
                text, keyboard = _format_faq_list(faqs, page=0)
                text = f"<b>FAQs in '{html.escape(category)}'</b>\n\n" + text.split("\n\n", 1)[1]
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                await query.edit_message_text(
                    f"<i>No FAQs found in category '{html.escape(category)}'.</i>",
                    parse_mode=ParseMode.HTML
                )

        elif action == "next":
            current_id = int(param)
            all_faqs = store.get_all()
            current_idx = next((i for i, f in enumerate(all_faqs) if f["id"] == current_id), -1)
            if current_idx >= 0 and current_idx < len(all_faqs) - 1:
                next_faq = all_faqs[current_idx + 1]
                text, keyboard = _format_faq_detail(next_faq, len(all_faqs))
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                # Stay on current FAQ
                faq = store.get_by_id(current_id)
                if faq:
                    text, keyboard = _format_faq_detail(faq, len(all_faqs))
                    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif action == "prev":
            current_id = int(param)
            all_faqs = store.get_all()
            current_idx = next((i for i, f in enumerate(all_faqs) if f["id"] == current_id), -1)
            if current_idx > 0:
                prev_faq = all_faqs[current_idx - 1]
                text, keyboard = _format_faq_detail(prev_faq, len(all_faqs))
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                # Stay on current FAQ
                faq = store.get_by_id(current_id)
                if faq:
                    text, keyboard = _format_faq_detail(faq, len(all_faqs))
                    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except Exception as e:
        logger.exception(f"Error in handle_faq_callback: {e}")


@error_handler
@admin_only
async def faq_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /faqadd command (admin only).

    Usage:
        /faqadd <question> | <answer>
        /faqadd --category <cat> <question> | <answer>
        /faqadd --keywords key1,key2 <question> | <answer>
    """
    if not update.message:
        return

    args = context.args or []

    if not args:
        await update.message.reply_text(
            "<b>Usage:</b> /faqadd &lt;question&gt; | &lt;answer&gt;\n\n"
            "<b>Options:</b>\n"
            "  --category &lt;cat&gt; - Set category\n"
            "  --keywords k1,k2 - Add keywords",
            parse_mode=ParseMode.HTML
        )
        return

    # Parse options
    category = "general"
    keywords: List[str] = []

    remaining_args = []
    i = 0
    while i < len(args):
        if args[i] == "--category" and i + 1 < len(args):
            category = args[i + 1]
            i += 2
        elif args[i] == "--keywords" and i + 1 < len(args):
            keywords = [k.strip() for k in args[i + 1].split(",")]
            i += 2
        else:
            remaining_args.append(args[i])
            i += 1

    # Parse question | answer
    full_text = " ".join(remaining_args)
    if "|" not in full_text:
        await update.message.reply_text(
            "Error: Use '|' to separate question and answer.\n"
            "Example: /faqadd What is X? | X is a thing.",
            parse_mode=ParseMode.HTML
        )
        return

    parts = full_text.split("|", 1)
    question = parts[0].strip()
    answer = parts[1].strip()

    if not question or not answer:
        await update.message.reply_text(
            "Error: Both question and answer are required.",
            parse_mode=ParseMode.HTML
        )
        return

    store = get_faq_store()
    new_faq = store.add(question=question, answer=answer, category=category, keywords=keywords)

    await update.message.reply_text(
        f"<b>FAQ Added!</b>\n\n"
        f"<b>ID:</b> {new_faq['id']}\n"
        f"<b>Question:</b> {html.escape(question)}\n"
        f"<b>Category:</b> {html.escape(category)}",
        parse_mode=ParseMode.HTML
    )


@error_handler
@admin_only
async def faq_update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /faqupdate command (admin only).

    Usage:
        /faqupdate <id> --question <new question>
        /faqupdate <id> --answer <new answer>
        /faqupdate <id> --category <new category>
    """
    if not update.message:
        return

    args = context.args or []

    if len(args) < 3:
        await update.message.reply_text(
            "<b>Usage:</b> /faqupdate &lt;id&gt; &lt;option&gt; &lt;value&gt;\n\n"
            "<b>Options:</b>\n"
            "  --question &lt;text&gt; - Update question\n"
            "  --answer &lt;text&gt; - Update answer\n"
            "  --category &lt;cat&gt; - Update category",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        faq_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Error: Invalid FAQ ID.", parse_mode=ParseMode.HTML)
        return

    # Parse update fields
    updates: Dict[str, Any] = {}
    i = 1
    while i < len(args):
        if args[i] == "--question" and i + 1 < len(args):
            # Collect all remaining args until next flag
            value_parts = []
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                value_parts.append(args[i])
                i += 1
            updates["question"] = " ".join(value_parts)
        elif args[i] == "--answer" and i + 1 < len(args):
            value_parts = []
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                value_parts.append(args[i])
                i += 1
            updates["answer"] = " ".join(value_parts)
        elif args[i] == "--category" and i + 1 < len(args):
            updates["category"] = args[i + 1]
            i += 2
        else:
            i += 1

    if not updates:
        await update.message.reply_text(
            "Error: No update fields specified.",
            parse_mode=ParseMode.HTML
        )
        return

    store = get_faq_store()
    if store.update(faq_id, **updates):
        await update.message.reply_text(
            f"<b>FAQ #{faq_id} Updated!</b>\n\n"
            f"<b>Updated fields:</b> {', '.join(updates.keys())}",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            f"<i>FAQ #{faq_id} not found.</i>",
            parse_mode=ParseMode.HTML
        )


@error_handler
@admin_only
async def faq_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /faqdelete command (admin only).

    Usage:
        /faqdelete <id>
    """
    if not update.message:
        return

    args = context.args or []

    if not args:
        await update.message.reply_text(
            "<b>Usage:</b> /faqdelete &lt;id&gt;",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        faq_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Error: Invalid FAQ ID.", parse_mode=ParseMode.HTML)
        return

    store = get_faq_store()
    if store.delete(faq_id):
        await update.message.reply_text(
            f"<b>FAQ #{faq_id} Deleted!</b>",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            f"<i>FAQ #{faq_id} not found.</i>",
            parse_mode=ParseMode.HTML
        )


@error_handler
@admin_only
async def faq_reorder_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /faqreorder command (admin only).

    Usage:
        /faqreorder <id> <new_position>
    """
    if not update.message:
        return

    args = context.args or []

    if len(args) < 2:
        await update.message.reply_text(
            "<b>Usage:</b> /faqreorder &lt;id&gt; &lt;new_position&gt;",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        faq_id = int(args[0])
        new_position = int(args[1])
    except ValueError:
        await update.message.reply_text(
            "Error: Invalid FAQ ID or position. Both must be numbers.",
            parse_mode=ParseMode.HTML
        )
        return

    store = get_faq_store()
    if store.reorder(faq_id, new_position):
        await update.message.reply_text(
            f"<b>FAQ #{faq_id} moved to position {new_position}!</b>",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            f"<i>FAQ #{faq_id} not found.</i>",
            parse_mode=ParseMode.HTML
        )


# Export for bot.py
__all__ = [
    "FAQStore",
    "get_faq_store",
    "faq_command",
    "handle_faq_callback",
    "faq_add_command",
    "faq_update_command",
    "faq_delete_command",
    "faq_reorder_command",
]
