/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2017-2024 Unrud <unrud@outlook.com>
 * Copyright © 2023-2024 Matthew Hana <matthew.hana@gmail.com>
 * Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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
 * Server address
 * @const
 * @type {string}
 */
export const SERVER = location.origin;

/**
 * Path of the root collection on the server (must end with /)
 * @const
 * @type {string}
 */
export const ROOT_PATH = location.pathname.replace(new RegExp("/+[^/]+/*(/index\\.html?)?$"), "") + '/';

/**
 * Regex to match and normalize color
 * @const
 */
export const COLOR_RE = new RegExp("^(#[0-9A-Fa-f]{6})(?:[0-9A-Fa-f]{2})?$");


/**
 * The text needed to confirm deleting a collection
 * @const
 */
export const DELETE_CONFIRMATION_TEXT = "DELETE";