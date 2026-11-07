# ATS gotchas

Field notes from real application runs. Read the section for the ATS you are on before the first click. When you learn a new one, add it here.

## All ATSs

- Read the whole job description, not the preview. Some postings ask applicants not to use generative AI; surface those to the user and do not auto-fill them.
- An on-page "thank you" regex is not proof of submission. Survey and EEO text often say "thank you". Confirm by URL change plus an email receipt.
- Some portals send no receipt at all. Record that in the tracker notes instead of waiting.
- Conditional fields appear after answers. Take a new snapshot after each answer that could reveal more fields.
- Chrome autofill and job extensions (Simplify, JobRight and similar) can write the user's saved values into a field the first time it gets focus, racing your own typing. In one dry run the Email box read back as the saved Gmail address with the intended address appended. Read back every field after filling it, and fill it again if it does not match exactly. Never click an extension's or the portal's "Autofill" button.
- Extension panels sit on top of the page and show the user's real name and resume. Crop screenshots to the form.
- Values set from JavaScript look filled and are not registered: Lever kept Submit dead and Ashby answered "Your form needs corrections" for JS-set fields. Click, type with real input, and click the popup option that appears for autocomplete, location and school fields. For radios and checkboxes, a real click on the visible control; `.checked = true` does not count.
- Text that arrives through `type_text` into a long box can be slow; CDP `Input.insertText` after a click is real input too, and the fallback for long answers that `fill` would set from JavaScript.
- Never reload a filled tab; on most ATSs it drops every unsaved answer.
- Multi-page and unfamiliar ATSs: after each step, check email for a receipt before you say "not submitted".

## Workday

- Escape on a dropdown can navigate away from the step. Never press it.
- Multiselect prompts need two real clicks: one to open, one on the option. Read back the chip that appears.
- Searchable prompts (school, country, "how did you hear") need a real Enter inside the prompt's own search box to run the search. This is the only allowed Enter. Press it only in that search box, then click the result, then confirm the page did not change step.
- "Autofill with resume" often pastes the Projects section into the last role's description and splits bullets mid-sentence. Replace each role description with that role's bullets, then check the Review page text for project names under any role.
- Re-editing a saved textarea can silently revert to the old value. Focus it, call `select()` on it, then CDP `Input.insertText` with the new text (real input), Save and Continue, then verify on the Review page rather than in the live field.
- Read the Review page text after autofill: each role description holds only that role's bullets, one per line, with no project names or a "Projects" heading under any role, and dates and "currently work here" match the resume. Report the Review text, not the live field value.
- Never press Tab while a dropdown is open: it commits the highlighted first option.
- Date spinbuttons need a real `fill`; the native value setter that is fine for text boxes breaks them.
- Option labels in skill and field-of-study prompts are not guessable ("Python (Programming Language)", "React.js"). Read the rendered options and match their text.
- Some prompts that look hierarchical are flat lists (`data-automation-id="promptLeafNode"`). Read the automation id before looking for children.
- Click Save and Continue as soon as a step is complete; only saved steps survive an accidental navigation.

## Greenhouse

- The newer `job-boards.greenhouse.io` form labels the phone country picker "Country", with options like "United States +1". It is not a country-of-residence question.
- Option text often adds an abbreviation, for example "Bachelor of Science (BS)" for a standing answer of "Bachelor of Science". That is the same answer, not a near match. Pick the option that matches the degree exactly, never the first "Bachelor..." option. A school that is not in the list is a near match problem: leave it empty and report it.
- School lists differ per board and load asynchronously. Type the school's name (then a shorter form of it), wait 3 to 5 seconds for options, and pick the exact school. Only if it never appears after waiting, leave School empty and say so; never pick a wrong school. Education dropdowns are filled even when optional.
- Forms carry an invisible reCAPTCHA (`g-recaptcha-response`). It can challenge only when Submit is pressed. Under auto-submit, a challenge after Submit is a CAPTCHA: park.
- Dropdowns are react-select. Type to filter, scroll the option into view, recompute its rectangle, hit-test the center with `document.elementFromPoint` to make sure the option is on top, click it, then read the selected value back. A blind click at an old position has picked the wrong demographic answer on real forms. Option lists for schools load asynchronously; wait a few seconds before deciding an option is absent. Never pick a near match.
- Conditional fields appear, for example a race question after "Hispanic or Latino" = No. Rescan after each answer.
- The cover letter "Enter manually" button has the same label as the resume one. Scope to the `#cover_letter` container.
- The file input clears itself after upload. Verify the attached filename or file size shown next to it, not the input's value.

## Lever

- Enter on a dropdown has submitted a real application. No Enter anywhere.
- hCaptcha often appears only when Submit is pressed. Under auto-submit, treat a CAPTCHA as a stop and hand it to the user.
- JS-set radios and checkboxes can leave Submit dead. Use real clicks.
- Confirm success by URL change and email receipt, not by "thank you" text.

## Phenom

- Next can record the application before the last step. Treat Next as Submit: stop at step 1, report the steps, and continue only with the user's approval. Check email after each step.

## Ashby

- The "autofill from resume" box is separate from the real resume input (`#_systemfield_resume`). Upload to the real input and confirm the filename.
- JS-set fields can produce "Your form needs corrections". Use real clicks and typing.

## iCIMS and one-click pages

- Some "Apply Now" buttons submit instantly with the profile's stored resume. Treat Apply Now as a final control on these pages. Read the page before clicking anything labelled Apply.

## Oracle, TI and other single-page forms

- Never assign the resume to an "Import your profile" (or "Autofill with resume") input. It re-imports the profile and wipes fields you already filled. Use the resume attachment input only.

## Buttons that lie

- A button labelled Submit can be a step-continue button, and a Next can record the application (Phenom). Report what the button looks like it does and treat both as final.
