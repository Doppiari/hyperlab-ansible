# A network refresh could loop while measuring the seal panel

Author: [importriri](https://github.com/importriri).

## Symptom

Replacing a five-network result with a smaller inventory including an unknown
mode triggered a QML height binding loop in the seal panel while Machines was
open. Both views observe the same network reader.

## Cause and correction

The rule label reserved three lines by dividing its laid-out content height by
its line count. Changing the text could invalidate those measurements while
evaluating the height itself. Measure the line height from the label's font
and take the larger of three lines and the text's natural height.

The Machines contract replaces the network result in an open workspace.
The runtime harness fails on QML binding warnings.
[Machine showcase contract](../tests/machine_showcase_contract.py)
