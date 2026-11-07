# Harbor Pi sources this path to select Node. The image already fixes Node.
# This is an environment shim, not an NVM installer or alternate runtime.
export PATH="/usr/local/bin:$PATH"
test "$(node --version)" = "v24.13.1" || return 1
