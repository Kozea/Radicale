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

/**
 * @param {import("../models/collection.js").Collection} collection
 * @returns str
 */
export function extract_title(collection) {
    if (collection.displayname && collection.displayname.length > 0) {
        return collection.displayname;
    } else
        return collection.href;
}

/**
 * @param {import("../models/collection.js").Collection} collection
 * @param {HTMLElement} title_element
 * @param {HTMLElement} description_element
 */
export function update_title_and_description(
    collection,
    title_element,
    description_element) {
    title_element.textContent = collection.displayname || collection.href;
    if (collection.description && collection.description.length > 0) {
        description_element.classList.remove("hidden");
        description_element.textContent = collection.description;
    } else {
        description_element.classList.add("hidden");
    }
}
