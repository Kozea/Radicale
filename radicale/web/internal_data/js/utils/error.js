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

/**
 * ErrorHandler manages error messages for a HTMLElement.
 */
export class ErrorHandler {
    /**
     * @param {HTMLElement} element
     */
    constructor(element) {
        /** @type {HTMLElement} */ this._element = element;
        /** @type {string} */ this._lastHTML = "anything_but_blank";
        this.clearError();
    }

    /**
     * Sets an error message for a given key.
     * @param {?string} errorMessage
     */
    setError(errorMessage) {
        if (errorMessage) {
            this._update([errorMessage]);
        } else {
            this.clearError();
        }
    }

    /**
     * Sets multiple error messages.
     * @param {string[]} errorMessages
     */
    setErrors(errorMessages) {
        this._update(errorMessages);
    }

    clearError() {
        this._update([]);
    }


    /**
     * Updates the element visibility and text content.
     * @param {string[]} errorMessages
     * @private
     */
    _update(errorMessages) {
        let html = "";
        if (errorMessages.length > 0) {
            html = errorMessages.join("<br>");
        }

        if (html !== this._lastHTML) {
            this._element.innerHTML = html;
            if (html) {
                this._element.classList.remove("hidden");
            } else {
                this._element.classList.add("hidden");
            }
            this._lastHTML = html;
        }
    }
}
