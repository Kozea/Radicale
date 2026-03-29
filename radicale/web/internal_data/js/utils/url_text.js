/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2017-2024 Unrud <unrud@outlook.com>
 * Copyright © 2023-2024 Matthew Hana <matthew.hana@gmail.com>
 * Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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

import { SERVER } from "../constants.js";

/**
 * Handles the display of URLs in input fields.
 */
export class UrlTextHandler {
    /**
     * @param {HTMLInputElement} element The input element to handle.
     */
    constructor(element) {
        this._element = element;
        this._element.addEventListener("focusin", () => {
            this._element.setSelectionRange(0, 99999);
        });
    }

    /**
     * Set the value of the input field to the given href.
     * If the href is relative, it will be prefixed with the server URL.
     * @param {string} href The href to set.
     */
    setHref(href) {
        if (href.startsWith("/")) {
            this._element.value = SERVER + href;
        } else if (!href.includes("://")) {
            // Handle cases where the href might not start with a slash
            this._element.value = SERVER + "/" + href;
        } else {
            this._element.value = href;
        }

        // Scroll the input all the way to the right so that the end of
        // the URL (the most important part) is visible.
        // Use a timeout to ensure that the layout has been calculated.
        setTimeout(() => {
            this._element.scrollLeft = this._element.scrollWidth;
        }, 0);
    }
}
