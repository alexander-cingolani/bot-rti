
import { useState } from "react";
import "../css/styles.css";
import '../css/navbar.css';

function Navbar() {
  const [isNavExpanded, setIsNavExpanded] = useState(false);

  return (
      <nav className="navigation">
          <a href="/" className="brand-name">
              MacroSoft
          </a>
          <button
              className="hamburger"
              onClick={() => {
                  setIsNavExpanded(!isNavExpanded);
              }}
          >
              {/* hamburger svg code... */}
          </button>
          <div className={isNavExpanded ? 'navigation-menu expanded' : 'navigation-menu'}>
              <ul>
                  <li>
                      <a href="/piloti">Home</a>
                  </li>
                  <li>
                      <a href="/scuderie">About</a>
                  </li>
                  <li>
                      <a href="/campionati">Contact</a>
                  </li>
              </ul>
          </div>
      </nav>
  );
}


export default function App() {
  return (
    <div>
      <Navbar />
      <div className="container">
        <article>
          <h1>What is Lorem Ipsum? </h1>
          Lorem Ipsum is simply dummy text of the printing and typesetting industry...
        </article>
      </div>
    </div>
  );
}

