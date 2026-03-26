---
applyTo: '**'
---
## Framework
*   **Framework:** Odoo
*   **Version:** 18.0
*   **Key Odoo 18 feature:** Use the new `display_name` compute method instead of the deprecated `name_get()` method for model display names.
*   **Odoo 18 XML views:** Use the new XML syntax and updated view inheritance patterns specific to Odoo 18.
*   **Odoo 18 API changes:** Adapt to any changes in the Odoo 18 API, including new decorators, method signatures, and model behaviors.
*   **Odoo 18 security:** Implement updated security practices, including access control lists (ACLs) and record rules, following Odoo 18 guidelines.
*   **Odoo 18 performance:** Optimize module performance by leveraging Odoo 18's new features and best practices.
*   **Odoo 18 testing:** Write tests using the updated Odoo 18 testing framework to ensure module reliability and compatibility.
*   **Odoo 18 documentation:** Update module documentation to reflect changes and new features in Odoo 18.
## General Development Instructions
*   When adding fields to models, always consider adding them to the search view if applicable. This enhances usability by allowing users to filter and search based on the new fields.
*   Use the `optional` attribute in XML views to allow users to customize their views by showing or hiding fields as needed. This improves the user experience by providing flexibility in how data is displayed.
*   Follow Odoo's best practices for module development, including proper naming conventions, code organization, and adherence to Odoo's coding standards.
