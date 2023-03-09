import { useState } from 'react';
import styles from "styles/joinForm.module.css"

export default function JoinUsForm({ isActive }: { isActive: boolean }) {
    if (isActive) {
        return (
            <form action="/send-data-here" method="post" className={styles.flex}>
                <label htmlFor="first">First name:</label>
                <input type="text" id="first" name="first" />
                <label htmlFor="last">Last name:</label>
                <input type="text" id="last" name="last" />
                <button type="submit">Submit</button>
            </form>
        );
    }
    return <></>;
}
