# CF_ROM_SYNC 0.2.5 LVS fix. Precheck run 15_NOV_2026___21_59_29 failed only
# LVS (stat 1). Netgen: CF_ROM_SYNC has 26 layout nets and 24 schematic nets.
# The schematic ties core vpb to vpwr and vnb to vgnd. The extracted abstract
# has neither port, so netgen inserts proxyvpb and proxyvnb. The well-pin
# rectangles in the 0.2.5 leaf are the same as the core LEF, and vpb still
# abuts the west met2 address rail. This script adds the labels and pin
# purpose, opens 140 nm between that rail and vpb, and straps the pins to the
# wrap rails. It does not touch the 6.9 µm DO/A stems. Idempotent.
#
# Magic names ports from text, and the catalog GDS has vpwr/vgnd text but
# not vpb/vnb. The schematic ties vpb to vpwr and vnb to vgnd.
#
# Coordinates are the wrap GDS database (1 nm). The core sits at (15000, 15000).
# vpb reaches the vpwr metal3 strap above the array. vnb reaches the vgnd strap.
# The via sits only on the matching rail.

layout = RBA::Layout::new
layout.read($gds)

core = layout.cell("CF_ROM_SYNC_core")
wrap = layout.cell("CF_ROM_SYNC")
raise "CF_ROM_SYNC_core missing" if core.nil?

text_layer = layout.layer(RBA::LayerInfo::new(69, 5))
met2 = layout.layer(RBA::LayerInfo::new(69, 20))
via2 = layout.layer(RBA::LayerInfo::new(69, 44))

def has_text(cell, layer, string)
  cell.shapes(layer).each do |shape|
    return true if shape.is_text? && shape.text.string == string
  end
  false
end

def add_text(cell, layer, string, x, y)
  text = RBA::Text::new(string, RBA::Trans::new(RBA::Point::new(x, y)))
  text.size = 0
  text.font = -1
  cell.shapes(layer).insert(text)
end

pin_layer = layout.layer(RBA::LayerInfo::new(69, 16))

def add_box(cell, layer, box)
  cell.shapes(layer).each do |shape|
    return if shape.is_box? && shape.box == box
  end
  cell.shapes(layer).insert(box)
end

# The vpb pin rectangle abuts the west met2 rail that ties the address pins
# together. Pull that rail back by the met2 spacing (140 nm) so the well pin
# is its own net before the strap lands on it.
def replace_box(cell, layer, old_box, new_box)
  found = false
  cell.shapes(layer).each do |shape|
    next unless shape.is_box? && shape.box == old_box
    shape.delete
    found = true
    break
  end
  add_box(cell, layer, new_box) if found || !cell.shapes(layer).each.any? { |s| s.is_box? && s.box == new_box }
end

unless core.nil?
  add_text(core, text_layer, "vpb", 2955, 59535) unless has_text(core, text_layer, "vpb")
  add_text(core, text_layer, "vnb", 25592, 59615) unless has_text(core, text_layer, "vnb")
  add_box(core, pin_layer, RBA::Box::new(610, 58820, 5300, 60250))
  add_box(core, pin_layer, RBA::Box::new(22925, 59000, 28260, 60230))
  replace_box(core, met2, RBA::Box::new(280, 0, 610, 60420), RBA::Box::new(280, 0, 470, 60420))
end

unless wrap.nil?
  straps = [
    # vpb metal2, from the pin up to the vpwr metal3 strap
    [met2, RBA::Box::new(17715, 74500, 18195, 82000)],
    # vpb via2, inside the vpwr metal3 strap only
    [via2, RBA::Box::new(17855, 81000, 18055, 81200)],
    # vnb metal2, from the pin up into the vgnd metal3 strap
    [met2, RBA::Box::new(40350, 74500, 40830, 77750)],
    # vnb via2, inside the vgnd metal3 strap
    [via2, RBA::Box::new(40490, 77000, 40690, 77200)]
  ]
  straps.each do |layer, box|
    present = false
    wrap.shapes(layer).each do |shape|
      present = true if shape.is_box? && shape.box == box
    end
    wrap.shapes(layer).insert(box) unless present
  end
end

layout.write($gds)
puts "strapped #{$gds}"
