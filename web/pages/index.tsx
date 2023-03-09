import Head from 'next/head';
import Header from '@/components/navbar';
import Layout from '@/components/layout';
import styles from '../styles/index.module.css';

import Footer from '@/components/footer';
import { MouseEventHandler, useState } from 'react';
import JoinUsForm from '@/components/joinForm';

function MainContent() {
    const [formActive, setFormActive] = useState(false);

    function onClick() {
        setFormActive(!formActive);
    }

    return (
        <>
            <div className={styles.container}>
                <h1 className={`${styles.maintext}`}>RACING TEAM ITALIA</h1>
                <p className={styles.subtext}>
                    Dal 2019 organizziamo campionati online su Gran Turismo per tutti i livelli
                </p>
                <JoinUsButton onClick={onClick} />
                <JoinUsForm isActive={formActive} />
            </div>
        </>
    );
}

function JoinUsButton({ onClick }: { onClick: MouseEventHandler }) {
    return (
        <button className={styles.joinus} onClick={onClick}>
            Unisciti a Noi
        </button>
    );
}

function Arrow() {
    return (
        <>
            <svg className={styles.arrow}>
                <path className={styles.a1} d="M0 0 L30 22 L60 0"></path>
                <path className={styles.a2} d="M0 20 L30 42 L60 20"></path>
                <path className={styles.a3} d="M0 40 L30 62 L60 40"></path>
            </svg>
        </>
    );
}

function UpComingRaces() {
    return <></>;
}

function Partners() {
    return <></>;
}

export default function Home() {
    return (
        <Layout>
            <Head>
                <title>Racing Team Italia</title>
                <meta name="description" content="Campionati Gran Turismo 7 e RaceRoom" />
                <meta name="author" content="Alexander Cingolani" />
                <meta name="keywords" content="GT7, Gran Turismo, Campionato" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <link rel="icon" href="/favicon.ico" />
            </Head>
            <main>
                <div className={styles.hero}>
                    <Header />
                    <MainContent />
                    <Arrow />
                    <UpComingRaces />
                    <Partners />
                    <Footer />
                </div>
            </main>
        </Layout>
    );
}
