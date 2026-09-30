# Parents and the Milk Stash

Baby Buddy can track pumped breast milk as a shared stash rather than something
that belongs to one child. This is useful for anyone who pumps into a shared
supply (for example, when feeding more than one baby from the same fridge or
freezer stock).

## Parents

A **Parent** is the person who pumps, breastfeeds or supplies milk. Parents
are separate from Children: they don't have a birth date, growth charts or
percentiles, but they do get their own page with pumping stats, breastfeeding
stats and stash activity.

To add a parent, go to **Family > Parents** and enter a first and (optional)
last name. Link the parent to one or more children on the same form (or later,
on the parent's edit page). A parent's page shows their linked children, a
breastfeeding summary, recent pumping, the milk stash summary, and buttons to
add pumping or a stash adjustment.

Each parent has a **Produces breast milk** checkbox (on by default). Only
parents with it ticked are offered wherever a parent is picked: who pumped,
who breastfed, and whose milk a stash entry is. When exactly one parent
produces breast milk, those fields are hidden everywhere and that parent is
filled in automatically (except on a discard, see
[below](#adding-to-and-removing-from-the-stash)); lists and the Milk stash page
then leave out the parent's name too, since it can only be them. A parent's
page only offers **Add pumping**, **Add to stash** and **Discard from stash**
when that parent produces breast milk.

## Logging pumping

Pumping is logged on a **parent**, not a child, since the milk doesn't belong
to a baby until it's fed to one. Start a pumping entry two ways:

- From the parent's page, using **Add pumping**.
- From a child's page, using **Add pumping**. If the child has exactly one
  linked parent, the form opens with that parent already selected. If the
  child has more than one linked parent, you're asked to pick one.

The pumping form has a **Store in stash** switch. When it's on, the full
pumped amount is added to the stash; an "Amount stored" field (under
"Advanced") lets you store only part of a session. Whether the switch starts
on or off is controlled by a site setting (see [Settings](#reports-and-settings)
below).

## Breastfeeding and the parent

Breastfeeding is recorded as a feeding whose method is **Left breast**,
**Right breast** or **Both breasts**. These methods show a **Breastfed by**
field for the parent who fed the baby; only parents who produce breast milk
count. When exactly one parent produces breast milk, the field is hidden and
that parent is filled in. Otherwise, on a new feeding, it's filled in
automatically when the baby has exactly one linked parent who produces breast
milk (also when you leave it blank); with none or more than one, pick the
parent yourself (or leave it blank). Changing the method away from a breast
method (to bottle, parent fed or self fed, the methods a stash feeding can
use) hides and clears the field, since it no longer applies.

A parent's page has a **Breastfeeding** card showing the session count and
total minutes for today and for the last 7 days, and the side used last.
Feeding two babies at the same time counts as two sessions, but their shared
minutes count once. Breastfeeding never touches the milk stash.

## Feedings from the stash

A breast milk (or fortified breast milk) feeding given by bottle, by a parent,
or self-fed can come from the stash; breastfeeding never does.
On the feeding form, a **Taken from stash** switch appears whenever the type
and method make it a candidate. Turning it on takes the full bottle amount out
of the stash; an "Amount from stash" field lets you take out only part of it.
Enter the bottle's amount (or the amount from the stash) when the switch is on.
For a new bottle, the switch starts on when the site setting is on and the
stash is already in use (pumped milk has been stored, or a stash adjustment
logged); until then it starts off, so a family that doesn't use the stash isn't
pushed below zero.

With **Taken from stash** on, an **Extra milk discarded** switch appears.
Turning it on adds an **Amount discarded** field (for milk that never reached
the baby: spilled, or left in an unfinished bottle; it comes out of the stash
on top of the amount fed) and an optional free-text
**Reason** (for example "Spilled" or "Left over"). This creates a stash entry
(a "stash adjustment") linked to the feeding, so the discarded amount stays
visible and editable on its own, and is never folded into the amount the baby
actually drank. A feeding has at most one discarded entry; turning the switch
off, or clearing the amount, removes it, and deleting the feeding removes it
too.

## Adding to and removing from the stash

Not every stash change comes from pumping or a bottle. Use **Add to stash** or
**Discard from stash** (on the parent page, on the Milk stash page, or
**Activities > Milk stash > + Stash adjustment**) to record things like:

- starting stock, donor milk, or a correction upward (**Added**)
- milk discarded outside of a feeding — spilled, left over, too old, given
  away, or any other correction downward (**Discarded**, with the same
  optional free-text reason as on a bottle)

Both kinds of entry have a **Parent** field: whose milk it is. When exactly
one parent produces breast milk, the field is hidden on the form and a new
**Added** entry is stored against that parent, since there's nobody else it
could belong to. A new **Discarded** entry is not: without a parent it takes
the oldest milk of anyone, which may be starting stock or milk of a parent who
no longer produces it (a lot's **Throw away** button fills in that lot's
parent instead). With more than one such parent, pick one (or leave it
blank). A stash entry is never logged against a
baby — a discard takes milk from the shared supply, so no baby drank it; the
only link to a baby is indirect, through the bottle a discard was logged at.

Stash adjustments are listed, and can be edited or deleted, like any other
entry: the Milk stash page links to the full list with **All stash
adjustments**.

## Milk age

The stash uses **FIFO, counted per millilitre**: each "lot" of milk in the
stash is one stored pumping session (or one **Added** entry), aged from when
it was logged. Nobody picks which lot a bottle or a discard comes from —
every withdrawal automatically takes its milk from the oldest lot first,
splitting a lot across several bottles or combining several lots into one
bottle as needed. The age shown always assumes the oldest milk really is used
first.

One exception: a **Discarded** entry with a parent takes that parent's
oldest milk first (and only then anyone's, if that parent's milk runs out).
Without a parent, a discard takes the oldest milk of anyone, like a bottle;
so does milk discarded at a bottle, which follows the bottle it came from.
The Milk stash page shows whose milk each lot is, and its **Throw away**
button fills in that lot's parent.

For example: two pumping sessions are stored in the stash, 120 ml and then
150 ml. A 70 ml bottle is given from the stash: it comes entirely from the
first (older) session, leaving 50 ml of it. A second 70 ml bottle empties that
remaining 50 ml and takes the other 20 ml from the second session, leaving
130 ml of the second session in the stash.

Two site-wide thresholds control how that age is shown, both on the **Milk
stash** page and the dashboard's stash card:

- After **48 hours** (by default) the oldest milk is marked **use first**,
  shown in orange.
- After **72 hours** (by default) it's marked **throw away**, shown in red,
  next to a **Throw away** button. It opens a new **Discarded** stash entry
  pre-filled with that lot's amount, the current time, and the reason "Older
  than 72 h" — all editable before saving. While any milk has expired, the
  Milk stash page also shows a **Throw away all expired milk** button that
  pre-fills the total expired amount instead, and the dashboard's stash card
  shows its own **Throw away** button for that same total.

The stash balance can go negative if milk was given before it was ever logged
as stored. While that's the case, the **Milk stash** page shows a dismissible
warning explaining the likely cause and the fix: an **Added** entry for the
starting amount, dated at or before the first bottle it covers. (Milk that
comes in after a shortfall makes up that shortfall first, so a starting entry
dated too late makes the remaining milk look younger than it really is.)
Dismissing the warning hides it in that browser until the balance is back at
or above zero; the next time the stash drops below zero it shows again. It
never appears anywhere except the Milk stash page, and only while the balance
is negative.

## Per-baby stash use

The stash is shared, but how much of it each baby drinks is shown per baby:

- a baby's dashboard has a **Milk from the stash** card with that baby's
  amount from the stash today and over the last 7 days;
- the Milk stash page's **Latest movements** list can be filtered to one
  baby's bottles with the **Baby** dropdown at the top;
- the **Milk From the Stash per Baby** report breaks this down per day, one
  series per baby.

## Reports and settings

Four reports cover the stash and pumping:

- **Milk Stash** — the stash balance over time.
- **Milk Stash In and Out** — how much was stored, added, drunk or discarded,
  per day.
- **Milk From the Stash per Baby** — stash milk drunk per day, one series per
  baby.
- **Pumping report** (on each parent's page) — pumping amounts for that
  parent.

Four site-wide settings, in the **Milk stash** section of **Site > Settings**,
control the defaults (the API exposes them at `/api/stash/settings`, which
apps use to show and change them):

| Setting | Default | Effect |
|---|---|---|
| Store pumped milk in the stash by default | On | Pre-selects "Store in stash" on new pumping entries |
| Take breast milk bottles from the stash by default | On | Pre-selects "Taken from stash" on new breast milk bottles once the stash is in use |
| Warn about stashed milk after (hours) | 48 | When the "use first" warning appears |
| Throw stashed milk away after (hours) | 72 | When the "throw away" alert appears |

## Existing (older) pumping data

Pumping entries created before parents existed are still linked to a child.
They keep working, and a banner appears on the pumping list while any
unassigned entries remain. Editing such an entry and choosing a parent moves
it onto that parent. To move them all at once, run:

```shell
python manage.py link_pumping_to_parents --parent <parent-slug>
```

Add `--child <child-slug>` (repeatable) to move only specific children's
entries, and `--dry-run` to see what would be moved without changing
anything. The command also reports how many moved entries overlap another
pumping entry of that parent (for example, one session that was logged once
per child), so duplicates can be cleaned up.

## Client compatibility

Older API clients that only know about child-based pumping keep working: a
pumping entry created with a `child` but no `parent` resolves the parent
automatically (as long as the child has exactly one linked parent who produces
breast milk, or only one parent produces breast milk at all) and is
stored against that parent, with `child` left empty. This means such a
pumping entry no longer shows up in that client's per-child pumping views,
since the stored entry now belongs to the parent, not the child. A client
that supports parents directly can detect that support through the API root
(see [API](../api.md)).
