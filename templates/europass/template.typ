#set page(margin: {{theme_margin_cm}}cm)
#set text(font: "{{theme_font}}", size: {{theme_size}}pt)

#align(center)[
  #text(size: {{theme_header_size}}pt, weight: "bold")[{{full_name}}]
]

#line(length: 100%, stroke: 0.5pt + rgb("003399"))

#grid(
  columns: (30%, 70%),
  gutter: 8pt,
  [*Email:*], [{{email}}],
  [*Phone:*], [{{phone}}],
  [*Location:*], [{{location}}],
)

#line(length: 100%, stroke: 0.5pt + rgb("003399"))

{{#if summary}}
== Personal Statement
{{summary}}
{{/if}}

{{#if experiences}}
== Work Experience
{{experiences}}
{{/if}}

{{#if education}}
== Education and Training
{{education}}
{{/if}}

{{#if skills}}
== Personal Skills
{{skills}}
{{/if}}

{{#if languages}}
== Language Skills
{{languages}}
{{/if}}

{{#if certifications}}
== Additional Information
{{certifications}}
{{/if}}

{{#if projects}}
== Projects
{{projects}}
{{/if}}
