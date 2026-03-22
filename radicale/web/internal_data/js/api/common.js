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
 * @param {XMLHttpRequest} request
 * @returns {string}
 */
export function to_error_message(request) {
    let have_status_text = (request.statusText != null && request.statusText != undefined && request.statusText != '')
    if ((request.status == 0) && (!have_status_text)) {
        return "Could not connect to server";
    }

    return request.status + " " + request.statusText;
}

/**
 * @param {string} method
 * @param {string} url
 * @param {?string} user
 * @param {?string} password
 * @returns {XMLHttpRequest}
 */
export function create_request(method, url, user, password) {
    let request = new XMLHttpRequest();
    if (user !== null && password !== null) {
        request.open(method, url, true, user, encodeURIComponent(password));
    } else {
        request.open(method, url, true);
    }
    return request;
}