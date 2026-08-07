"""Backend-owned demo data used by the HTTP contract.

The application is intentionally stateless for this phase, but keeping the
fixture here makes the boundary explicit: the browser receives repository
content only through API responses.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


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


INITIAL_MESSAGES = [
    {
        "id": "message_welcome",
        "role": "assistant",
        "content": "Hi! I’m ready to help you understand this codebase. Ask me about the architecture, a feature, or where a particular behavior lives.",
    },
    {
        "id": "message_checkout_question",
        "role": "user",
        "content": "How does the checkout flow work?",
    },
    {
        "id": "message_checkout_answer",
        "role": "assistant",
        "content": "A checkout starts in the API layer, validates the cart, and then coordinates payment and inventory before creating the order. The controller keeps orchestration thin: the domain services own the actual side effects.\n\nIf payment fails, the order is never created. Inventory is reserved only after payment succeeds, and a failed reservation triggers a payment refund.",
        "citations": [
            {"file": "src/api/checkout.ts", "start_line": 5, "end_line": 20},
            {"file": "src/services/payment-service.ts", "start_line": 1, "end_line": 13},
        ],
    },
]


def tree_fixture() -> list[dict[str, Any]]:
    return deepcopy(DEMO_TREE)


def messages_fixture() -> list[dict[str, Any]]:
    return deepcopy(INITIAL_MESSAGES)

