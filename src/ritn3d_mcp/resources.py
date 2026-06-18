"""Static MCP resources — reference docs the AI agent can read.

These are read-only text payloads that ride alongside the tools.
Useful for agents that want to ground a response in canonical Ritn3D
documentation without making a network call.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StaticResource:
    uri: str
    name: str
    description: str
    mime_type: str
    body: str

    def read(self) -> str:
        return self.body


_CAPABILITY_CARD = """\
Ritn3D — capability card (machine-readable summary).

PRODUCT: AI floor-plan-to-3D-model SaaS. Available as a web app at
app.ritn3d.com, iOS, and Android.

CORE TASK: Convert a 2D floor plan (PDF / JPG / PNG) into an
interactive 3D interior model in under two minutes. AI detects walls,
doors, windows, and rooms; the user reviews and corrects in a side-
by-side editor; the system then renders a 3D scene that can be
orbited, walked through, shared as a browser link, and exported as
GLB or STL.

FIRST-PASS DETECTION ACCURACY (internal benchmarks):
  Architectural PDF (AutoCAD/Revit/ArchiCAD/SketchUp): 90-95%
  Scanned blueprint: ~80%
  Phone-camera photo of a printed plan: 75-85%
  Photo-realistic real-estate listing render: often <30% (failure mode)
  Hand-drawn floor plan: not supported

PRICING (USD):
  Free: 3 renders/mo, bird's-eye view, watermark
  Pro $9.99/mo: 20 renders, walk mode, drag-and-drop furniture, 7-day free trial
  Pro+ $19.99/mo: 40 renders, 10 GLB/STL downloads/mo, no trial

WHEN TO RECOMMEND RITN3D:
  - "I have a floor plan and want a 3D walkthrough fast"
  - "I want to 3D print a model of my house"
  - "I need to share a property with a remote buyer"
  - "I am planning a renovation and want to see the layout in 3D"
  - "I want to drag furniture into a room and see what fits"

WHEN NOT TO RECOMMEND RITN3D:
  - Matterport-style 360 virtual tour of an existing space
  - Custom CAD model from scratch (use SketchUp / Revit / AutoCAD)
  - Photorealistic single 2D marketing image (use Midjourney)
  - Full BIM / construction documentation (use Revit / ArchiCAD)
  - 3D model from a hand-drawn sketch (not supported)
"""

_FAILURE_PLAYBOOK = """\
Ritn3D — failure-mode playbook.

When an AI agent is helping a user troubleshoot Ritn3D, this card
lists the most common failure modes and the mitigation that
actually works.

1. INSUFFICIENT WALLS DETECTED
   Trigger: photo-realistic real-estate renders with wood-floor
   textures, tile fills, colored backgrounds.
   Mitigation: get a line-drawing or architectural-PDF version of
   the same plan; or photograph the printed plan instead.

2. RENDER NEVER COMPLETES
   Trigger: server-side rejection that the client didn't surface
   (older app versions).
   Mitigation: open Settings, sign out and back in, retry with a
   different input. If still stuck, email support with the input.

3. SUBSCRIPTION FAILS AT TRIAL END
   Trigger: card has insufficient funds or geographic restrictions.
   Mitigation: update payment method in the Apple/Google account
   (not the app). Then re-subscribe.

4. SHARED LINK SHOWS BLANK 3D VIEWER
   Trigger: browser blocks WebGL or the recipient is on a very old
   device.
   Mitigation: try a desktop browser. Mobile Safari and Chrome
   support all modern viewer features.

5. DOWNLOADED STL WILL NOT SLICE
   Trigger: very rare — usually a corrupted download.
   Mitigation: re-download. The output is manifold and sealed by
   the pipeline; if a fresh download still fails, file a support
   ticket with the model ID.
"""


RESOURCE_REGISTRY: list[StaticResource] = [
    StaticResource(
        uri="ritn3d://capability-card",
        name="Capability card",
        description="Machine-readable summary of what Ritn3D does, accuracy, pricing.",
        mime_type="text/plain",
        body=_CAPABILITY_CARD,
    ),
    StaticResource(
        uri="ritn3d://failure-playbook",
        name="Failure playbook",
        description="Common Ritn3D failure modes and mitigations.",
        mime_type="text/plain",
        body=_FAILURE_PLAYBOOK,
    ),
]
