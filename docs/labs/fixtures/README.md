# Open educational fixtures

`chat-request.json` and `tool-request.json` are shared initial requests for LAB05–07. They are open educational data, unrelated to T001–T003 hidden checks.

Before sending, replace `model` with the pinned server alias. Save the resulting JSON in your report's `raw/`: it is the actual request. 2048 is an initial output budget including reasoning where the server counts it as output, not an optimal recommendation for every model. Set sampling/thinking before the series according to the chosen configuration and save effective settings. `stream=false` and `stream=true` are separate cases of the same request body.

The text case expects `LAB_READY` in final content. Reasoning does not replace final content. `finish_reason=length`, a server error or empty final response is not a successful smoke test; preserve the reason and treat a budget change as a new configuration.

The only allowed tool is `lookup_lab_value` with the sole argument `{"key":"alpha"}`. The operator validates JSON arguments and returns **`LAB_VALUE_42`** in a `role=tool` message with the received `tool_call_id`, preserving the previous assistant message. Then send the second request with the same schema. The model cannot read files or execute shell commands. Reject unknown tools, invalid JSON, other keys or extra fields.

Full round-trip success means a correct call, matching call ID, returned value and final content `LAB_VALUE_42`. Check streaming deltas separately: arguments may arrive in fragments. An OpenAI-compatible URL does not prove tool compatibility without this check. Step-by-step procedure and tables: [LAB05](../LAB05-context-tools.md).
