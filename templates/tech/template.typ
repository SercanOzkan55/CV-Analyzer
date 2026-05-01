#set page(margin: {{theme_margin_cm}}cm)
#set text(font: "{{theme_font}}", size: {{theme_size}}pt)

= {{full_name}}
{{email}} | {{phone}} | {{location}}

{{#if summary}}
== Technical Summary
{{summary}}
{{/if}}

{{#if experiences}}
== Engineering Experience
{{experiences}}
{{/if}}

{{#if skills}}
== Technical Skills
{{skills}}
{{/if}}

{{#if education}}
== Education
{{education}}
{{/if}}
