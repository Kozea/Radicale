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
 * @enum {string}
 */
export const CollectionType = {
    PRINCIPAL: "PRINCIPAL",
    ADDRESSBOOK: "ADDRESSBOOK",
    CALENDAR_JOURNAL_TASKS: "CALENDAR_JOURNAL_TASKS",
    CALENDAR_JOURNAL: "CALENDAR_JOURNAL",
    CALENDAR_TASKS: "CALENDAR_TASKS",
    JOURNAL_TASKS: "JOURNAL_TASKS",
    CALENDAR: "CALENDAR",
    JOURNAL: "JOURNAL",
    TASKS: "TASKS",
    WEBCAL: "WEBCAL",
    is_subset: function(a, b) {
        let components = a.split("_");
        for (let i = 0; i < components.length; i++) {
            if (b.search(components[i]) === -1) {
                return false;
            }
        }
        return true;
    },
    union: function(a, b) {
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
    },
    valid_options_for_type: function(a){
        a = a.trim().toUpperCase();
        switch(a){
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
};

/**
 * @constructor
 * @struct
 * @param {string} href Must always start and end with /.
 * @param {CollectionType} type
 * @param {string} displayname
 * @param {string} description
 * @param {string} color
 */
export function Collection(href, type, displayname, description, color, contentcount, size, source) {
    this.href = href;
    this.type = type;
    this.displayname = displayname;
    this.color = color;
    this.description = description;
    this.source = source;
    this.contentcount = contentcount;
    this.size = size;
}