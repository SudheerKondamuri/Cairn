# Guest helpers

These fixed scripts are copied into a Celesto guest before an investigation.
They are the only guest-side command entry points used by the control plane.
Arguments arrive as URL-safe base64 values, so a model-supplied HTTP payload
cannot become shell syntax at the control-plane command boundary.
