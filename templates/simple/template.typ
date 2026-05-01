#set page(margin: {{theme_margin_cm}}cm)
#set text(font: "{{theme_font}}", size: {{theme_size}}pt)

#text(size: {{theme_header_size}}pt, weight: "bold")[{{full_name}}]

{{email}} | {{phone}} | {{location}}

{{#if summary}}
== Summary
{{summary}}
{{/if}}

{{#if experiences}}
== Work Experience
{{experiences}}
{{/if}}

{{#if education}}
== Education
{{education}}
{{/if}}

{{#if skills}}
== Skills
{{skills}}
{{/if}}

{{#if certifications}}
== Certifications
{{certifications}}
{{/if}}

{{#if languages}}
== Languages
{{languages}}
{{/if}}
