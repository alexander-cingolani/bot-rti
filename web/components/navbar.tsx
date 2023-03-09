import Link from 'next/link';
import Image from 'next/image';
import styles from 'styles/navbar.module.css';
import homeLogo from '../public/partners/rti-small.png';
import facebookLogo from '../public/logos/facebook.svg';
import twitchLogo from '../public/logos/twitch.svg';
import instagramLogo from '../public/logos/instagram.svg';
import youtubeLogo from '../public/logos/youtube.svg';
import { Turn as Hamburger } from 'hamburger-react';
import { useState } from 'react';
import { useRouter } from 'next/router';

function HomeLink() {
    const router = useRouter();
    if (router.asPath != '/') {
        return (
            <Link href={'/'}>
                <Image src={homeLogo} width={'100'} height={'40'} alt="home"></Image>
            </Link>
        );
    }
    return <></>;
}

function Navbar() {
    const [open, setOpen] = useState(false);
    const toggleNavbar = () => {
        setOpen(!open);
    };
    return (
        <>
            <nav className={styles.nav}>
                <ul className={styles.navbar}>
                    <li>
                        <Link href="/drivers">Piloti</Link>
                    </li>
                    <li>
                        <Link href="/championships">Campionati</Link>
                    </li>
                    <li>
                        <Link href="/teams">Scuderie</Link>
                    </li>

                    <li>
                        <Link
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label="twitch channel"
                            href="https://www.twitch.tv/racingteamitalia"
                        >
                            <Image src={twitchLogo} alt="" width={'45'} height={'45'}></Image>
                        </Link>
                    </li>
                    <li>
                        <Link
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label="youtube channel"
                            href="https://www.youtube.com/c/RacingTeamItalia"
                        >
                            <Image src={youtubeLogo} alt="" width={'45'} height={'45'}></Image>
                        </Link>
                    </li>
                    <li>
                        <Link
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label="facebook page"
                            href="https://www.facebook.com/groups/RacingTeamItalia"
                        >
                            <Image src={facebookLogo} alt="" width={'45'} height={'45'} />
                        </Link>
                    </li>
                    <li>
                        <Link
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label="facebook page"
                            href="https://www.instagram.com/rti_racingteamitalia"
                        >
                            <Image src={instagramLogo} alt="" width={'45'} height={'45'}></Image>
                        </Link>
                    </li>
                </ul>

                <div className={styles.mobile}>
                    <Hamburger />
                </div>
            </nav>
        </>
    );
}

export default function Header() {
    return (
        <header className={`${styles.primary_header} ${styles.flex}`}>
            <HomeLink />
            <Navbar />
        </header>
    );
}
