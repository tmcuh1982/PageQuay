"""Bounded native Window slots mapped to their DOM-owned Playwright frames."""

from .errors import PQError

MAX_DEPTH = 32
MAX_OWNERS = 128
SELECTOR = "pq_frame_slot"
# Registered with content_script=True: Playwright's isolated utility realm.
# Return handles only, never page text/attributes. No DOM writes or page evaluate.
FRAME_SLOT_ENGINE = """(() => {
  const query = (root, selector) => {
    if (selector === 'overflow') return window.length > 128 ? document.documentElement : null;
    const index = Number(selector);
    if (!Number.isInteger(index) || index < 0 || index >= 128 || index >= window.length)
      return null;
    const child = window[index];
    let visited = 0, owners = 0;
    const find = current => {
      // Native selector returns node references in the renderer, no strings/body
      // transferred. A large unrelated DOM does not consume the frame-owner budget.
      for (const node of current.querySelectorAll('iframe,frame')) {
        if (++owners > 128) throw new Error('Frame owner inventory limit');
        if (node.contentWindow === child) return node;
      }
      const walker = document.createTreeWalker(current, NodeFilter.SHOW_ELEMENT);
      let node;
      while ((node = walker.nextNode())) {
        if (++visited > 2000) throw new Error('Frame shadow inventory limit');
        if (node.shadowRoot) {
          const found = find(node.shadowRoot);
          if (found) return found;
        }
      }
      return null;
    };
    return find(root);
  };
  return { query, queryAll(root, selector) {
    const node = query(root, selector); return node ? [node] : [];
  }};
})()"""


async def register_frame_selector(playwright):
    await playwright.selectors.register(SELECTOR, FRAME_SLOT_ENGINE, content_script=True)


async def frame_path(frame):
    path = []
    current = frame
    while current.parent_frame is not None:
        if len(path) >= MAX_DEPTH:
            raise PQError(
                "UNAVAILABLE",
                "Frame nesting exceeds read limit",
                503,
                details={"cause": "WORLD_NOT_FOUND"},
            )
        parent = current.parent_frame
        if await parent.locator(f"{SELECTOR}=overflow").count():
            raise PQError(
                "UNAVAILABLE",
                "Frame owner inventory exceeds read limit",
                503,
                details={"cause": "WORLD_NOT_FOUND"},
            )
        found = False
        for index in range(MAX_OWNERS):
            locator = parent.locator(f"{SELECTOR}={index}")
            if not await locator.count():
                continue
            handle = await locator.element_handle(timeout=100)
            if handle is None:
                continue
            try:
                if await handle.content_frame() == current:
                    path.append(index)
                    found = True
                    break
            finally:
                await handle.dispose()
        if not found:
            raise PQError(
                "UNAVAILABLE",
                "Frame owner not present in current DOM",
                503,
                details={"cause": "WORLD_NOT_FOUND"},
            )
        current = parent
    return path[::-1]


def bounded_path(value):
    if (
        isinstance(value, list)
        and len(value) <= MAX_DEPTH
        and all(type(index) is int and 0 <= index < MAX_OWNERS for index in value)
    ):
        return list(value)
    return None
