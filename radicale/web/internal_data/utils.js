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
 * Escape string for usage in XML
 * @param {string} s
 * @return {string}
 */
export function escape_xml(s) {
    return (s
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&apos;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;"));
}

/**
 * @return {string}
*/
export function random_uuid() {
    return random_hex(8) + "-" + random_hex(4) + "-" + random_hex(4) + "-" + random_hex(4) + "-" + random_hex(12);
}

/**
 * Generate random hex number.
 * @param {number} length
 * @return {string}
 */
export function random_hex(length) {
    let bytes = new Uint8Array(Math.ceil(length / 2));
    window.crypto.getRandomValues(bytes);
    return bytes.reduce((s, b) => s + b.toString(16).padStart(2, "0"), "").substring(0, length);
}

/**
 * Removed invalid HREF characters for a collection HREF.
 *
 * @param a A valid Input element or an onchange Event of an Input element.
 */
export function cleanHREFinput(a) {
    let href_form = a;
    if (a.target) {
        href_form = a.target;
    }
    let currentTxtVal = href_form.value.trim().toLowerCase();
    //Clean the HREF to remove not permitted chars
    currentTxtVal = currentTxtVal.replace(/(?![0-9a-z\-\_\.])./g, '');
    //Clean the HREF to remove leading . (would result in hidden directory)
    currentTxtVal = currentTxtVal.replace(/^\./, '');
    href_form.value = currentTxtVal;
}

/**
 * Checks if a proposed HREF for a collection has a valid format and syntax.
 *
 * @param href String of the porposed HREF.
 *
 * @return Boolean results if the HREF is valid.
 */
export function isValidHREF(href) {
    if (href.length < 1) {
        return false;
    }
    if (href.indexOf("/") != -1) {
        return false;
    }

    return true;
}

/**
 * Format bytes to human-readable text.
 *
 * @param bytes Number of bytes.
 *
 * @return Formatted string.
 */
export function bytesToHumanReadable(bytes, dp=1) {
    let isNumber = !isNaN(parseFloat(bytes)) && !isNaN(bytes - 0);
    if(!isNumber){
        return "";
    }
    var i = bytes == 0 ? 0 : Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(dp) * 1 + ' ' + ['b', 'kb', 'mb', 'gb', 'tb'][i];
}