/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2026-2026 Max Berger <max@berger.name>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

import { ErrorHandler } from "./error.js";

/**
 * Manages form validation by running validation functions on input fields.
 */
export class FormValidator {

    /**
     * @param {ErrorHandler} error_handler
     */
    constructor(error_handler) {
        this.error_handler = error_handler;
        this.validation_methods = [];
    }

    /**
     * @param {HTMLInputElement} field
     * @param {function(): ?string} validation_method
     */
    addValidator(field, validation_method) {
        this.validation_methods.push({ field, validation_method });
        field.addEventListener("input", () => {
            this.validate();
        });
        this.validate();
    }

    /**
     * Validates all added validators.
     * @returns true if all validators are valid
     */
    validate() {
        let errorMessages = [];
        for (let { field, validation_method } of this.validation_methods) {
            let errorMessage = validation_method(field);
            if (errorMessage) {
                errorMessages.push(errorMessage);
            }
        }
        this.error_handler.setErrors(errorMessages);
        return errorMessages.length === 0;
    }
}

/**
 * Validates that the input is not empty.
 * @param {HTMLInputElement} input 
 * @param {string} field_name 
 * @returns{function(): ?string}
 */
export function validate_non_empty(input, field_name) {
    return () => {
        if (input.value) {
            return null;
        }
        return field_name + " is empty";
    };
}




