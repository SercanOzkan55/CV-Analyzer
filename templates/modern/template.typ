#set page(margin: {{theme_margin_cm}}cm)
#set text(font: "{{theme_font}}", size: {{theme_size}}pt)

#align(center)[
  #text(size: {{theme_header_size}}pt, weight: "bold")[{{full_name}}]
  {{email}} | {{phone}} | {{location}}
]

{{#if summary}}
== Profile
{{summary}}
{{/if}}

{{#if experiences}}
== Experience
{{experiences}}
{{/if}}

{{#if skills}}
== Skills
{{skills}}
{{/if}}

{{#if education}}
== Education
{{education}}
{{/if}}
