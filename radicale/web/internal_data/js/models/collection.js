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

export class CollectionType {
    // Private Fields
    static #_PRINCIPAL = "PRINCIPAL";
    static #_ADDRESSBOOK = "ADDRESSBOOK";
    static #_CALENDAR_JOURNAL_TASKS = "CALENDAR_JOURNAL_TASKS";
    static #_CALENDAR_JOURNAL = "CALENDAR_JOURNAL";
    static #_CALENDAR_TASKS = "CALENDAR_TASKS";
    static #_JOURNAL_TASKS = "JOURNAL_TASKS";
    static #_CALENDAR = "CALENDAR";
    static #_JOURNAL = "JOURNAL";
    static #_TASKS = "TASKS";
    static #_WEBCAL = "WEBCAL";

    // Accessors for "get" functions only (no "set" functions)
    static get PRINCIPAL() { return this.#_PRINCIPAL; }
    static get ADDRESSBOOK() { return this.#_ADDRESSBOOK; }
    static get CALENDAR_JOURNAL_TASKS() { return this.#_CALENDAR_JOURNAL_TASKS; }
    static get CALENDAR_JOURNAL() { return this.#_CALENDAR_JOURNAL; }
    static get CALENDAR_TASKS() { return this.#_CALENDAR_TASKS; }
    static get JOURNAL_TASKS() { return this.#_JOURNAL_TASKS; }
    static get CALENDAR() { return this.#_CALENDAR; }
    static get JOURNAL() { return this.#_JOURNAL; }
    static get TASKS() { return this.#_TASKS; }
    static get WEBCAL() { return this.#_WEBCAL; }

    static is_subset(/** @type {string} */ a, /** @type {string} */ b) {
        let components = a.split("_");
        for (let i = 0; i < components.length; i++) {
            if (b.search(components[i]) === -1) {
                return false;
            }
        }
        return true;
    }

    static union(/** @type {string} */ a, /** @type {string} */ b) {
        if (a.search(this.ADDRESSBOOK) !== -1 || b.search(this.ADDRESSBOOK) !== -1) {
            if (a && a !== this.ADDRESSBOOK || b && b !== this.ADDRESSBOOK) {
                throw "Invalid union: " + a + " " + b;
            }
            return this.ADDRESSBOOK;
        }
        let union = [];
        if (a.search(this.CALENDAR) !== -1 || b.search(this.CALENDAR) !== -1) {
            union.push(this.CALENDAR);
        }
        if (a.search(this.JOURNAL) !== -1 || b.search(this.JOURNAL) !== -1) {
            union.push(this.JOURNAL);
        }
        if (a.search(this.TASKS) !== -1 || b.search(this.TASKS) !== -1) {
            union.push(this.TASKS);
        }
        if (a.search(this.WEBCAL) !== -1 || b.search(this.WEBCAL) !== -1) {
            union.push(this.WEBCAL);
        }
        return union.join("_");
    }

    /**
     * @param {string} a
     */
    static valid_options_for_type(a) {
        a = a.trim().toUpperCase();
        switch (a) {
            case CollectionType.CALENDAR_JOURNAL_TASKS:
            case CollectionType.CALENDAR_JOURNAL:
            case CollectionType.CALENDAR_TASKS:
            case CollectionType.JOURNAL_TASKS:
            case CollectionType.CALENDAR:
            case CollectionType.JOURNAL:
            case CollectionType.TASKS:
                return [CollectionType.CALENDAR_JOURNAL_TASKS, CollectionType.CALENDAR_JOURNAL, CollectionType.CALENDAR_TASKS, CollectionType.JOURNAL_TASKS, CollectionType.CALENDAR, CollectionType.JOURNAL, CollectionType.TASKS];
            case CollectionType.ADDRESSBOOK:
            case CollectionType.WEBCAL:
            default:
                return [a];
        }
    }
}

export class Permission {
    // Private Fields
    static #_WRITE_PROPERTIES = "D:write-properties";
    static #_SHARE_MAP = "RADICALE:share-map";
    static #_SHARE_TOKEN = "RADICALE:share-token";

    // Accessors for "get" functions only (no "set" functions)
    static get WRITE_PROPERTIES() { return this.#_WRITE_PROPERTIES; }
    static get SHARE_MAP() { return this.#_SHARE_MAP; }
    static get SHARE_TOKEN() { return this.#_SHARE_TOKEN; }
}


export class Collection {
    /**
     * @param {string} href Must always start and end with /.
     * @param {string} type
     * @param {string} displayname
     * @param {string} description
     * @param {string} color
     * @param {number} contentcount
     * @param {number} size
     * @param {string} source
     * @param {Array<string>} permissions
     * @param {string} version
     */
    constructor(href, type, displayname, description, color, contentcount, size, source, permissions, version = "") {
        this.href = href;
        this.type = type;
        this.displayname = displayname;
        this.color = color;
        this.description = description;
        this.source = source;
        this.contentcount = contentcount;
        this.size = size;
        this.permissions = permissions;
        this.version = version;
    }

    has_permission(/** @type {string} */ permission) {
        if (!this.permissions) {
            return false;
        }
        return this.permissions.includes(permission);
    }
}