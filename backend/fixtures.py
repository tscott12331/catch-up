"""Backend-owned demo data used by the HTTP contract.

The application is intentionally stateless for this phase, but keeping the
fixture here makes the boundary explicit: the browser receives repository
content only through API responses.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

try:
    from .models import Citation, Conversation, Message, Repository, SourcePassage
except ImportError:  # Allows ``uv run main.py`` from the backend directory.
    from models import Citation, Conversation, Message, Repository, SourcePassage


DEMO_REPOSITORY_ID = UUID("11111111-1111-4111-8111-111111111111")
DEMO_CONVERSATION_ID = UUID("22222222-2222-4222-8222-222222222222")
DEMO_REVISION = "8a8b1b9f95ea2f76e67c11b79f138b5e8044be57"
CHECKOUT_PASSAGE_ID = UUID("33333333-3333-4333-8333-333333333333")
PAYMENT_PASSAGE_ID = UUID("44444444-4444-4444-8444-444444444444")


DEMO_TREE: list[dict[str, Any]] = [
    {
        "name": "src",
        "type": "folder",
        "children": [
            {
                "name": "api",
                "type": "folder",
                "children": [
                    {"name": "checkout.ts", "type": "file"},
                    {"name": "orders.ts", "type": "file"},
                    {"name": "users.ts", "type": "file"},
                ],
            },
            {
                "name": "services",
                "type": "folder",
                "children": [
                    {"name": "payment-service.ts", "type": "file"},
                    {"name": "inventory-service.ts", "type": "file"},
                ],
            },
            {"name": "server.ts", "type": "file"},
            {"name": "config.ts", "type": "file"},
        ],
    },
    {
        "name": "tests",
        "type": "folder",
        "children": [
            {"name": "checkout.test.ts", "type": "file"},
            {"name": "orders.test.ts", "type": "file"},
        ],
    },
    {"name": "README.md", "type": "file"},
    {"name": "package.json", "type": "file"},
    {"name": "docker-compose.yml", "type": "file"},
]


FILE_CONTENT: dict[str, str] = {
    "src/api/checkout.ts": "\n".join(
        [
            'import { paymentService } from "../services/payment-service";',
            'import { inventoryService } from "../services/inventory-service";',
            'import { orderRepository } from "../repositories/order-repository";',
            "",
            "export async function checkout(request: CheckoutRequest) {",
            "  const cart = await cartService.get(request.cartId);",
            "  validateCart(cart);",
            "",
            "  const payment = await paymentService.charge({",
            "    customerId: request.customerId,",
            "    amount: cart.total,",
            "  });",
            "",
            "  try {",
            "    await inventoryService.reserve(cart.items);",
            "    return orderRepository.create({ cart, payment });",
            "  } catch (error) {",
            "    await paymentService.refund(payment.id);",
            "    throw error;",
            "  }",
        ]
    ),
    "src/services/payment-service.ts": "\n".join(
        [
            "export const paymentService = {",
            "  async charge(input: ChargeInput) {",
            "    const result = await stripe.paymentIntents.create({",
            "      amount: input.amount,",
            "      customer: input.customerId,",
            "    });",
            "",
            "    return { id: result.id, status: result.status };",
            "  },",
            "",
            "  async refund(paymentId: string) {",
            "    return stripe.refunds.create({ payment_intent: paymentId });",
            "  },",
            "};",
        ]
    ),
    "src/api/orders.ts": "export async function createOrder(input: OrderInput) {\n  return orderRepository.create(input);\n}",
    "src/api/users.ts": "export async function getUser(userId: string) {\n  return userRepository.get(userId);\n}",
    "src/services/inventory-service.ts": "export const inventoryService = {\n  async reserve(items: CartItem[]) {\n    return inventory.reserve(items);\n  },\n};",
    "src/server.ts": "import { app } from \"./app\";\n\napp.listen(process.env.PORT ?? 3000);",
    "src/config.ts": "export const config = {\n  environment: process.env.NODE_ENV ?? \"development\",\n};",
    "tests/checkout.test.ts": "it(\"creates an order after payment and inventory\", async () => {\n  await expect(checkout(request)).resolves.toBeDefined();\n});",
    "tests/orders.test.ts": "it(\"persists an order\", async () => {\n  await expect(createOrder(input)).resolves.toBeDefined();\n});",
    "README.md": "# Checkout service\n\nA small service that coordinates payment, inventory, and order creation.",
    "package.json": '{"name":"checkout-service","private":true}',
    "docker-compose.yml": "services:\n  app:\n    build: .",
}


STARTER_QUESTIONS = [
    "Where is authentication handled?",
    "Give me a map of the main services",
]


def tree_fixture() -> list[dict[str, Any]]:
    return deepcopy(DEMO_TREE)


def conversation_fixture(repository_id: UUID) -> Conversation:
    return Conversation(id=DEMO_CONVERSATION_ID, repository_id=repository_id)


def passages_fixture(repository_id: UUID) -> list[SourcePassage]:
    return [
        SourcePassage(
            id=CHECKOUT_PASSAGE_ID,
            repository_id=repository_id,
            revision=DEMO_REVISION,
            path="src/api/checkout.ts",
            start_line=5,
            end_line=20,
            content="\n".join(FILE_CONTENT["src/api/checkout.ts"].splitlines()[4:20]),
        ),
        SourcePassage(
            id=PAYMENT_PASSAGE_ID,
            repository_id=repository_id,
            revision=DEMO_REVISION,
            path="src/services/payment-service.ts",
            start_line=1,
            end_line=13,
            content=FILE_CONTENT["src/services/payment-service.ts"],
        ),
    ]


def citation_fixture(passage: SourcePassage, *, identifier: UUID) -> Citation:
    return Citation(
        id=identifier,
        passage_id=passage.id,
        revision=passage.revision,
        path=passage.path,
        start_line=passage.start_line,
        end_line=passage.end_line,
    )


def messages_fixture(repository_id: UUID, conversation_id: UUID | None = None) -> list[Message]:
    conversation = conversation_fixture(repository_id).model_copy(update={"id": conversation_id}) if conversation_id else conversation_fixture(repository_id)
    checkout, payment = passages_fixture(repository_id)
    return [
        Message(
            id=UUID("55555555-5555-4555-8555-555555555555"),
            conversation_id=conversation.id,
            role="assistant",
            content="Hi! I’m ready to help you understand this codebase. Ask me about the architecture, a feature, or where a particular behavior lives.",
            completion_state="completed",
        ),
        Message(
            id=UUID("66666666-6666-4666-8666-666666666666"),
            conversation_id=conversation.id,
            role="user",
            content="How does the checkout flow work?",
            completion_state="completed",
        ),
        Message(
            id=UUID("77777777-7777-4777-8777-777777777777"),
            conversation_id=conversation.id,
            role="assistant",
            content="A checkout starts in the API layer, validates the cart, and then coordinates payment and inventory before creating the order. The controller keeps orchestration thin: the domain services own the actual side effects.\n\nIf payment fails, the order is never created. Inventory is reserved only after payment succeeds, and a failed reservation triggers a payment refund.",
            completion_state="completed",
            citations=[
                citation_fixture(checkout, identifier=UUID("88888888-8888-4888-8888-888888888888")),
                citation_fixture(payment, identifier=UUID("99999999-9999-4999-8999-999999999999")),
            ],
        ),
    ]


def validate_fixture_integrity(repository: Repository) -> None:
    passages = {passage.id: passage for passage in passages_fixture(repository.id)}
    for message in messages_fixture(repository.id):
        for citation in message.citations:
            passage = passages[citation.passage_id]
            assert passage.repository_id == repository.id
            assert passage.revision == citation.revision
            assert passage.path == citation.path
            assert passage.start_line <= citation.start_line <= citation.end_line <= passage.end_line
