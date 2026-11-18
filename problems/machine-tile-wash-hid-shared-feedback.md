# The Machine tile wash hid the shared card feedback

## Observation

Machine tiles changed their border on hover but kept the same fill on hover
and press. Other interactive cards lightened their fill in both states.

## Cause and fix

The tile replaced ShellCard's entire colour binding to add a domain wash.
That replacement kept selection but lost the inherited pointer feedback.
ShellCard now exposes its existing handler states as readonly properties;
MachineTile uses those same handlers to lighten its wash by the shared 5%
neutral mix. Selection keeps the 8% mix and takes precedence. Disabled tiles
keep their resting fill. No extra pointer handler or activation route is added.

## Regression proof

The executable showcase contract first failed on the missing hover feedback.
It sends real Qt pointer motion, press and release, checks the exact fill in
each state, and checks the return to the resting wash and disabled behaviour.
Removing pointer feedback or either exposed handler state fails the contract,
as does losing selection's precedence. The resting domain mix is checked
separately at exactly 7%, so feedback cannot conceal an excessive domain fill.
