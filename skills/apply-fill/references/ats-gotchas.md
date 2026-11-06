# ATS gotchas

Field notes from real application runs. Read the section for the ATS you are on before the first click. When you learn a new one, add it here.

## All ATSs

- Read the whole job description, not the preview. Some postings ask applicants not to use generative AI; surface those to the user and do not auto-fill them.
- An on-page "thank you" regex is not proof of submission. Survey and EEO text often say "thank you". Confirm by URL change plus an email receipt.
- Some portals send no receipt at all. Record that in the tracker notes instead of waiting.
- Conditional fields appear after answers. Take a new snapshot after each answer that could reveal more fields.

## Workday

- Escape on a dropdown can navigate away from the step. Never press it.
- Multiselect prompts need two real clicks: one to open, one on the option. Read back the chip that appears.
- Searchable prompts (school, country, "how did you hear") need a real Enter inside the prompt's own search box to run the search. This is the only allowed Enter. Press it only in that search box, then click the result, then confirm the page did not change step.
- "Autofill with resume" often pastes the Projects section into the last role's description and splits bullets mid-sentence. Replace each role description with that role's bullets, then check the Review page text for project names under any role.
- Re-editing a saved textarea can silently revert to the old value. Select the text and insert with a CDP-level fill, save, then verify on the Review page rather than in the live field.

## Greenhouse

- Dropdowns are react-select. Type to filter, scroll the option into view, recompute its rectangle, hit-test the center with `document.elementFromPoint` to make sure the option is on top, click it, then read the selected value back. Option lists for schools load asynchronously; wait a few seconds before deciding an option is absent. Never pick a near match.
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
